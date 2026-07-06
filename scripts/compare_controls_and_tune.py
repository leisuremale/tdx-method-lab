"""Compare V1 against simple controls, then run a small parameter sweep."""

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

from export_signal_events import build_universe
from tdx_lab.backtest import benchmark_buy_hold, simulate
from tdx_lab.data import fetch_daily_tencent
from tdx_lab.indicators import compute_xhmain, compute_xhsub

COST = 0.0013


def cross_up(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    out = np.zeros(len(a), dtype=bool)
    for i in range(1, len(a)):
        out[i] = np.isfinite(a[i]) and np.isfinite(b[i]) and a[i] > b[i] and a[i - 1] <= b[i - 1]
    return out


def signal_metrics(
    df: pd.DataFrame,
    entry: np.ndarray,
    *,
    hold_days: int | None = None,
    exit_signal: np.ndarray | None = None,
    min_hold_days: int = 3,
    confirm_days: int = 2,
    cooldown_days: int = 5,
) -> dict[str, Any]:
    c = df["close"].to_numpy()
    o = df["open"].to_numpy()
    dates = df["date"].to_numpy()
    n = len(df)

    equity = np.ones(n)
    holding = False
    entry_idx = 0
    entry_price = 0.0
    shares = 0.0
    cooldown = 0
    exit_count = 0
    trades: list[dict[str, Any]] = []

    for i in range(34, n):
        if holding:
            held = i - entry_idx
            should_exit = False
            if hold_days is not None and held >= hold_days:
                should_exit = True
            if exit_signal is not None:
                exit_count = exit_count + 1 if exit_signal[i] else 0
                if held >= min_hold_days and exit_count >= confirm_days:
                    should_exit = True

            if should_exit:
                exit_price = min(o[i], c[i])
                equity[i] = shares * exit_price * (1 - COST)
                holding = False
                cooldown = cooldown_days
                ret = (exit_price / entry_price - 1) * 100
                trades.append(
                    {
                        "entry_date": dates[entry_idx],
                        "exit_date": dates[i],
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "return_pct": round(ret, 2),
                        "hold_days": held,
                    }
                )
            else:
                equity[i] = shares * c[i]
        else:
            equity[i] = equity[i - 1]
            if cooldown > 0:
                cooldown -= 1
            elif entry[i]:
                entry_price = c[i]
                shares = equity[i - 1] * (1 - COST) / entry_price
                equity[i] = shares * entry_price
                holding = True
                entry_idx = i
                exit_count = 0

    eq = equity[34:]
    total_return = float((eq[-1] - 1.0) * 100)
    peak = np.maximum.accumulate(eq)
    max_drawdown = float(np.min((eq / peak - 1.0) * 100))
    if not trades:
        calmar = 0.0
    elif max_drawdown < 0:
        calmar = total_return / abs(max_drawdown)
    else:
        calmar = math.inf

    win_rate = 0.0
    avg_return = 0.0
    avg_hold = 0.0
    if trades:
        returns = [t["return_pct"] for t in trades]
        win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
        avg_return = float(np.mean(returns))
        avg_hold = float(np.mean([t["hold_days"] for t in trades]))

    return {
        "n_trades": len(trades),
        "win_rate": round(win_rate, 2),
        "total_return": round(total_return, 2),
        "max_drawdown": round(max_drawdown, 2),
        "calmar": round(calmar, 2),
        "avg_return": round(avg_return, 2),
        "avg_hold_days": round(avg_hold, 1),
    }


def random_entries(template: np.ndarray, code: str) -> np.ndarray:
    n = len(template)
    count = int(template[34:].sum())
    out = np.zeros(n, dtype=bool)
    if count <= 0:
        return out
    rng = np.random.default_rng(abs(hash(code)) % (2**32))
    choices = rng.choice(np.arange(34, n), size=min(count, n - 34), replace=False)
    out[choices] = True
    return out


def stock_strategy_rows(stock: Any, df: pd.DataFrame) -> list[dict[str, Any]]:
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    bh = benchmark_buy_hold(df)

    zhz = sub["zhz"]
    macd_zero = np.zeros(len(df), dtype=bool)
    macd_zero[1:] = (zhz[1:] > 0) & (zhz[:-1] <= 0)
    kdj_any = cross_up(sub["az3"], sub["az4"])
    take_profit_or_trend_down = np.zeros(len(df), dtype=bool)
    take_profit_or_trend_down[1:] = sub["guan_bian"][1:] < sub["guan_bian"][:-1]
    take_profit_or_trend_down |= main["trend_down"]

    strategies: list[tuple[str, dict[str, Any]]] = [
        (
            "v1_tianma_exit",
            simulate(df, sub, main, entry_rules="tian_ma_only", exit_rules="take_profit_or_trend_down"),
        ),
        ("tianma_hold_10", signal_metrics(df, sub["tian_ma"], hold_days=10)),
        ("tianma_hold_20", signal_metrics(df, sub["tian_ma"], hold_days=20)),
        ("macd_zero_hold_10", signal_metrics(df, macd_zero, hold_days=10)),
        ("kdj_any_hold_10", signal_metrics(df, kdj_any, hold_days=10)),
        ("random_same_freq_hold_10", signal_metrics(df, random_entries(sub["tian_ma"], stock.code), hold_days=10)),
    ]

    rows = []
    for strategy, result in strategies:
        rows.append(
            {
                "strategy": strategy,
                "code": stock.code,
                "name": stock.name,
                "segment": stock.segment,
                "n_trades": result["n_trades"],
                "win_rate": result["win_rate"],
                "total_return": result["total_return"],
                "max_drawdown": result["max_drawdown"],
                "calmar": result["calmar"],
                "avg_return": result["avg_return"],
                "avg_hold_days": result["avg_hold_days"],
                "bh_return": bh["total_return"],
                "vs_bh": round(result["total_return"] - bh["total_return"], 2),
            }
        )
    return rows


def tune_rows(stock: Any, df: pd.DataFrame) -> list[dict[str, Any]]:
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    bh = benchmark_buy_hold(df)
    rows = []

    for threshold in [10, 15, 20, 25, 30]:
        entry = cross_up(sub["az3"], sub["az4"]) & (sub["az3"] < threshold)
        for hold_days in [5, 10, 20, 30]:
            result = signal_metrics(df, entry, hold_days=hold_days)
            rows.append(
                {
                    "strategy": "low_kdj_fixed_hold",
                    "threshold": threshold,
                    "hold_days": hold_days,
                    "code": stock.code,
                    "name": stock.name,
                    "segment": stock.segment,
                    "n_trades": result["n_trades"],
                    "win_rate": result["win_rate"],
                    "total_return": result["total_return"],
                    "max_drawdown": result["max_drawdown"],
                    "calmar": result["calmar"],
                    "avg_return": result["avg_return"],
                    "bh_return": bh["total_return"],
                    "vs_bh": round(result["total_return"] - bh["total_return"], 2),
                }
            )

    for confirm_days in [1, 2, 3]:
        for cooldown_days in [0, 3, 5, 10]:
            result = simulate(
                df,
                sub,
                main,
                entry_rules="tian_ma_only",
                exit_rules="take_profit_or_trend_down",
                confirm_days=confirm_days,
                cooldown_days=cooldown_days,
            )
            rows.append(
                {
                    "strategy": "tianma_signal_exit",
                    "threshold": 20,
                    "hold_days": -1,
                    "confirm_days": confirm_days,
                    "cooldown_days": cooldown_days,
                    "code": stock.code,
                    "name": stock.name,
                    "segment": stock.segment,
                    "n_trades": result["n_trades"],
                    "win_rate": result["win_rate"],
                    "total_return": result["total_return"],
                    "max_drawdown": result["max_drawdown"],
                    "calmar": result["calmar"],
                    "avg_return": result["avg_return"],
                    "bh_return": bh["total_return"],
                    "vs_bh": round(result["total_return"] - bh["total_return"], 2),
                }
            )
    return rows


def aggregate(rows: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    out = []
    for key, group in rows.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        total_trades = int(group["n_trades"].sum())
        weighted_win = float((group["win_rate"] * group["n_trades"]).sum() / total_trades) if total_trades else 0.0
        row = dict(zip(group_cols, key))
        row.update(
            {
                "stocks": len(group),
                "stocks_with_trades": int((group["n_trades"] > 0).sum()),
                "trades": total_trades,
                "weighted_win_rate": round(weighted_win, 2),
                "positive_stocks": int((group["total_return"] > 0).sum()),
                "beat_bh_stocks": int((group["vs_bh"] > 0).sum()),
                "median_return": round(float(group["total_return"].median()), 2),
                "median_drawdown": round(float(group["max_drawdown"].median()), 2),
                "median_calmar": round(float(group["calmar"].median()), 2),
                "median_vs_bh": round(float(group["vs_bh"].median()), 2),
            }
        )
        out.append(row)
    return pd.DataFrame(out).sort_values(["median_calmar", "median_return"], ascending=[False, False])


def write_report(path: Path, controls: pd.DataFrame, tuning: pd.DataFrame) -> None:
    lines = [
        "# V1 Controls And Tuning",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Universe: Feishu AI basket, common-account tradable, excluding 688.",
        "",
        "## Control Comparison",
        "",
        "| 策略 | 股票数 | 有交易股票 | 交易数 | 加权胜率 | 正收益股 | 跑赢BH | 中位收益 | 中位回撤 | 中位Calmar | 中位vsBH |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in controls.to_dict("records"):
        lines.append(
            f"| {row['strategy']} | {row['stocks']} | {row['stocks_with_trades']} | {row['trades']} | "
            f"{row['weighted_win_rate']:.2f}% | {row['positive_stocks']} | {row['beat_bh_stocks']} | "
            f"{row['median_return']:.2f}% | {row['median_drawdown']:.2f}% | {row['median_calmar']:.2f} | {row['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Tuning Top 20",
            "",
            "| 策略 | threshold | hold_days | confirm | cooldown | 交易数 | 加权胜率 | 正收益股 | 跑赢BH | 中位收益 | 中位回撤 | 中位Calmar | 中位vsBH |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in tuning.head(20).to_dict("records"):
        lines.append(
            f"| {row['strategy']} | {row.get('threshold', '')} | {row.get('hold_days', '')} | "
            f"{row.get('confirm_days', '')} | {row.get('cooldown_days', '')} | {row['trades']} | "
            f"{row['weighted_win_rate']:.2f}% | {row['positive_stocks']} | {row['beat_bh_stocks']} | "
            f"{row['median_return']:.2f}% | {row['median_drawdown']:.2f}% | {row['median_calmar']:.2f} | {row['median_vs_bh']:.2f}% |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    control_rows: list[dict[str, Any]] = []
    tune_grid_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for stock in build_universe():
        if "ai_basket" not in stock.source:
            continue
        try:
            df = fetch_daily_tencent(stock.code, count=500)
            if df.empty or len(df) < 120:
                raise RuntimeError("empty or insufficient data")
            control_rows.extend(stock_strategy_rows(stock, df))
            tune_grid_rows.extend(tune_rows(stock, df))
        except Exception as exc:
            failures.append(f"{stock.code} {stock.name}: {exc}")

    controls_raw = pd.DataFrame(control_rows)
    tuning_raw = pd.DataFrame(tune_grid_rows)
    controls = aggregate(controls_raw, ["strategy"])
    tuning = aggregate(tuning_raw, ["strategy", "threshold", "hold_days", "confirm_days", "cooldown_days"])

    controls_raw.to_csv(reports / "v1_controls_by_stock.csv", index=False)
    controls.to_csv(reports / "v1_controls_summary.csv", index=False)
    tuning_raw.to_csv(reports / "v1_tuning_by_stock.csv", index=False)
    tuning.to_csv(reports / "v1_tuning_summary.csv", index=False)
    write_report(reports / "v1_controls_tuning.md", controls, tuning)

    print(f"stocks={controls['stocks'].max() if not controls.empty else 0} failures={len(failures)}")
    print(reports / "v1_controls_tuning.md")
    if failures:
        print("\n".join(failures[:10]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
