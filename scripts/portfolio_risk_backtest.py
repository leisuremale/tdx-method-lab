"""Portfolio-level risk test for the operational V1 candidate."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for path in [ROOT / "src", ROOT / "scripts"]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_operational_system import BLOCKED_SEGMENTS, POLICY_BY_SEGMENT
from compare_controls_and_tune import cross_up
from export_signal_events import build_universe
from test_market_regime_filters import align_regime, build_basket_index
from tdx_lab.data import fetch_daily_tencent
from tdx_lab.indicators import atr, compute_xhmain, compute_xhsub


def prepare_stock(stock: Any, df: pd.DataFrame, basket: pd.DataFrame) -> pd.DataFrame | None:
    policy = POLICY_BY_SEGMENT.get(stock.segment)
    if not policy or stock.segment in BLOCKED_SEGMENTS:
        return None

    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    regime = align_regime(df, basket)
    close = df["close"].astype(float)
    ma20 = close.rolling(20).mean().to_numpy()
    ma55 = close.rolling(55).mean().to_numpy()
    a = atr(df["high"].to_numpy(), df["low"].to_numpy(), close.to_numpy(), 20)

    entry = cross_up(sub["az3"], sub["az4"]) & (sub["az3"] < 25)
    down = regime["down"].to_numpy(dtype=bool)
    bull = regime["bull"].to_numpy(dtype=bool)
    base_exit = (~sub["hold_line"]) | main["trend_down"]

    exit_signal = base_exit.copy()
    if policy == "bull_delay_ma20":
        exit_signal = np.where(bull, close.to_numpy() < ma20, base_exit)
    elif policy == "bull_no_sell_until_ma20":
        exit_signal = np.where(bull, close.to_numpy() < ma20, base_exit)
    elif policy == "adaptive_ma55_no_down":
        entry = entry & ~down
        exit_signal = np.where(bull, close.to_numpy() < ma55, base_exit)
    elif policy == "adaptive_shou_no_down":
        entry = entry & ~down
        exit_signal = np.where(bull, ~sub["shou_cang"], base_exit)

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["date"]),
            "code": stock.code,
            "name": stock.name,
            "segment": stock.segment,
            "policy": policy,
            "close": close,
            "entry": entry,
            "exit": exit_signal,
            "atr20": a,
        }
    )
    return out


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((equity / peak) - 1).min() * 100)


def portfolio_metrics(curve: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    if curve.empty:
        return {}
    equity = curve["equity"]
    ret = float((equity.iloc[-1] / equity.iloc[0] - 1) * 100)
    dd = max_drawdown(equity)
    calmar = ret / abs(dd) if dd < 0 else math.inf
    wins = int((trades["return_pct"] > 0).sum()) if not trades.empty else 0
    return {
        "total_return": round(ret, 2),
        "max_drawdown": round(dd, 2),
        "calmar": round(calmar, 2),
        "n_trades": len(trades),
        "win_rate": round(wins / len(trades) * 100, 2) if len(trades) else 0.0,
        "avg_trade_return": round(float(trades["return_pct"].mean()), 2) if len(trades) else 0.0,
    }


def simulate_portfolio(
    signals: dict[str, pd.DataFrame],
    *,
    stop_mode: str,
    max_positions: int = 5,
    max_per_segment: int = 2,
    min_hold_days: int = 20,
    confirm_days: int = 4,
    initial_cash: float = 1_000_000.0,
    cost: float = 0.0013,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    dates = sorted(set().union(*(set(s["date"]) for s in signals.values())))
    by_code = {code: df.set_index("date") for code, df in signals.items()}
    cash = initial_cash
    positions: dict[str, dict[str, Any]] = {}
    equity_rows = []
    trades = []

    def mark_equity(date: pd.Timestamp) -> float:
        value = cash
        for code, pos in positions.items():
            df = by_code[code]
            if date in df.index:
                value += pos["shares"] * float(df.loc[date, "close"])
            else:
                value += pos["last_value"]
        return value

    for date in dates:
        # mark latest position values
        for code, pos in list(positions.items()):
            df = by_code[code]
            if date in df.index:
                pos["last_price"] = float(df.loc[date, "close"])
                pos["last_value"] = pos["shares"] * pos["last_price"]

        # exits first
        for code, pos in list(positions.items()):
            df = by_code[code]
            if date not in df.index:
                continue
            row = df.loc[date]
            price = float(row["close"])
            pos["hold_days"] += 1
            if bool(row["exit"]):
                pos["exit_count"] += 1
            else:
                pos["exit_count"] = 0

            stop_hit = False
            if stop_mode == "fixed_8pct":
                stop_hit = price <= pos["entry_price"] * 0.92
            elif stop_mode == "atr2":
                stop_hit = price <= pos["entry_price"] - 2 * pos["entry_atr"]
            elif stop_mode == "trail_20pct":
                pos["peak_price"] = max(pos["peak_price"], price)
                stop_hit = price <= pos["peak_price"] * 0.80

            indicator_exit = pos["hold_days"] >= min_hold_days and pos["exit_count"] >= confirm_days
            if stop_hit or indicator_exit:
                cash += pos["shares"] * price * (1 - cost)
                ret = (price / pos["entry_price"] - 1) * 100
                trades.append(
                    {
                        "code": code,
                        "name": pos["name"],
                        "segment": pos["segment"],
                        "entry_date": pos["entry_date"].date().isoformat(),
                        "exit_date": date.date().isoformat(),
                        "entry_price": round(pos["entry_price"], 2),
                        "exit_price": round(price, 2),
                        "return_pct": round(ret, 2),
                        "hold_days": pos["hold_days"],
                        "exit_reason": "stop" if stop_hit else "indicator",
                        "stop_mode": stop_mode,
                    }
                )
                del positions[code]

        equity = mark_equity(date)
        seg_counts: dict[str, int] = {}
        for pos in positions.values():
            seg_counts[pos["segment"]] = seg_counts.get(pos["segment"], 0) + 1

        # entries after exits
        candidates = []
        for code, df in by_code.items():
            if code in positions or date not in df.index:
                continue
            row = df.loc[date]
            if bool(row["entry"]):
                candidates.append((code, row))
        candidates.sort(key=lambda item: (item[1]["segment"], item[0]))

        for code, row in candidates:
            if len(positions) >= max_positions:
                break
            segment = str(row["segment"])
            if seg_counts.get(segment, 0) >= max_per_segment:
                continue
            price = float(row["close"])
            entry_atr = float(row["atr20"]) if np.isfinite(row["atr20"]) else price * 0.08
            target_value = equity / max_positions
            spend = min(cash, target_value)
            if spend < 10_000:
                continue
            shares = (spend * (1 - cost)) / price
            cash -= spend
            positions[code] = {
                "name": row["name"],
                "segment": segment,
                "entry_date": date,
                "entry_price": price,
                "entry_atr": entry_atr,
                "shares": shares,
                "hold_days": 0,
                "exit_count": 0,
                "peak_price": price,
                "last_price": price,
                "last_value": shares * price,
            }
            seg_counts[segment] = seg_counts.get(segment, 0) + 1

        equity_rows.append({"date": date.date().isoformat(), "equity": mark_equity(date), "cash": cash, "positions": len(positions)})

    curve = pd.DataFrame(equity_rows)
    trade_df = pd.DataFrame(trades)
    metrics = portfolio_metrics(curve, trade_df)
    metrics["stop_mode"] = stop_mode
    return curve, trade_df, metrics


def write_report(path: Path, summary: pd.DataFrame) -> None:
    lines = [
        "# Portfolio Risk Backtest",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Rules: validated segments only, max 5 positions, max 2 positions per segment, equal-weight target position, manual-confirm system proxy.",
        "",
        "| stop_mode | return | max_dd | Calmar | trades | win | avg_trade |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in summary.to_dict("records"):
        lines.append(
            f"| {r['stop_mode']} | {r['total_return']:.2f}% | {r['max_drawdown']:.2f}% | {r['calmar']:.2f} | "
            f"{int(r['n_trades'])} | {r['win_rate']:.2f}% | {r['avg_trade_return']:.2f}% |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    stocks = [s for s in build_universe() if "ai_basket" in s.source]
    data = {}
    by_code = {s.code: s for s in stocks}
    for stock in stocks:
        df = fetch_daily_tencent(stock.code, count=500)
        if not df.empty and len(df) >= 300:
            data[stock.code] = df
    basket = build_basket_index(data)

    signals = {}
    for code, df in data.items():
        prepared = prepare_stock(by_code[code], df, basket)
        if prepared is not None:
            signals[code] = prepared

    metrics = []
    for stop_mode in ["none", "fixed_8pct", "atr2", "trail_20pct"]:
        curve, trades, row = simulate_portfolio(signals, stop_mode=stop_mode)
        curve.to_csv(reports / f"v1_portfolio_curve_{stop_mode}.csv", index=False)
        trades.to_csv(reports / f"v1_portfolio_trades_{stop_mode}.csv", index=False)
        metrics.append(row)

    summary = pd.DataFrame(metrics).sort_values(["calmar", "total_return"], ascending=[False, False])
    summary.to_csv(reports / "v1_portfolio_risk_summary.csv", index=False)
    write_report(reports / "v1_portfolio_risk_backtest.md", summary)
    print(summary.to_string(index=False))
    print(reports / "v1_portfolio_risk_backtest.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
