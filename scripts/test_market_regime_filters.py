"""Test market/sector trend filters for the V1 combo candidate."""

from __future__ import annotations

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

from compare_controls_and_tune import aggregate, cross_up, signal_metrics
from export_signal_events import build_universe
from tdx_lab.backtest import benchmark_buy_hold
from tdx_lab.data import fetch_daily_tencent
from tdx_lab.indicators import compute_xhmain, compute_xhsub


def build_basket_index(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    series = []
    for code, df in data.items():
        s = df.set_index("date")["close"].astype(float)
        s = s / s.iloc[0]
        series.append(s.rename(code))
    panel = pd.concat(series, axis=1).sort_index()
    index = panel.mean(axis=1, skipna=True)
    out = pd.DataFrame({"date": index.index, "basket_index": index.values})
    out["ma60"] = out["basket_index"].rolling(60).mean()
    out["ret60"] = out["basket_index"] / out["basket_index"].shift(60) - 1
    out["bull"] = (out["basket_index"] > out["ma60"]) & (out["ret60"] > 0.20)
    out["down"] = (out["basket_index"] < out["ma60"]) & (out["ret60"] < 0)
    out["up"] = (out["basket_index"] > out["ma60"]) & ~out["bull"]
    return out


def align_regime(df: pd.DataFrame, basket: pd.DataFrame) -> pd.DataFrame:
    regime = basket.set_index("date")[["bull", "down", "up", "basket_index", "ret60"]]
    aligned = regime.reindex(pd.to_datetime(df["date"])).ffill().fillna(False)
    return aligned.reset_index(drop=True)


def rolling_windows(df: pd.DataFrame, window: int = 250, step: int = 60) -> list[tuple[str, pd.DataFrame]]:
    out = []
    start = 0
    while start + window <= len(df):
        part = df.iloc[start : start + window].reset_index(drop=True)
        label = f"{pd.to_datetime(part['date'].iloc[0]).date()}_{pd.to_datetime(part['date'].iloc[-1]).date()}"
        out.append((label, part))
        start += step
    if out and pd.to_datetime(out[-1][1]["date"].iloc[-1]).date() != pd.to_datetime(df["date"].iloc[-1]).date():
        part = df.iloc[-window:].reset_index(drop=True)
        label = f"{pd.to_datetime(part['date'].iloc[0]).date()}_{pd.to_datetime(part['date'].iloc[-1]).date()}"
        out.append((label, part))
    return out


def window_regime(regime: pd.DataFrame) -> str:
    bull = float(regime["bull"].mean())
    down = float(regime["down"].mean())
    if bull >= 0.5:
        return "basket_bull"
    if down >= 0.5:
        return "basket_down"
    return "basket_neutral"


def strategy_result(df: pd.DataFrame, regime: pd.DataFrame, strategy: str) -> dict[str, Any]:
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    close = df["close"].astype(float)
    ma20 = close.rolling(20).mean().to_numpy()
    ma55 = close.rolling(55).mean().to_numpy()

    entry = cross_up(sub["az3"], sub["az4"]) & (sub["az3"] < 25)
    base_exit = (~sub["hold_line"]) | main["trend_down"]
    bull = regime["bull"].to_numpy(dtype=bool)
    down = regime["down"].to_numpy(dtype=bool)

    exit_signal = base_exit
    min_hold_days = 20
    confirm_days = 4

    if strategy == "base_combo":
        pass
    elif strategy == "no_new_entries_in_down":
        entry = entry & ~down
    elif strategy == "bull_delay_ma20":
        bull_exit = close.to_numpy() < ma20
        exit_signal = np.where(bull, bull_exit, base_exit)
    elif strategy == "bull_delay_ma55":
        bull_exit = close.to_numpy() < ma55
        exit_signal = np.where(bull, bull_exit, base_exit)
    elif strategy == "adaptive_ma20_no_down":
        entry = entry & ~down
        bull_exit = close.to_numpy() < ma20
        exit_signal = np.where(bull, bull_exit, base_exit)
    elif strategy == "adaptive_ma55_no_down":
        entry = entry & ~down
        bull_exit = close.to_numpy() < ma55
        exit_signal = np.where(bull, bull_exit, base_exit)
    elif strategy == "adaptive_shou_no_down":
        entry = entry & ~down
        bull_exit = ~sub["shou_cang"]
        exit_signal = np.where(bull, bull_exit, base_exit)
    elif strategy == "bull_no_sell_until_ma20":
        bull_exit = close.to_numpy() < ma20
        exit_signal = np.where(bull, bull_exit, base_exit)
        confirm_days = 3
    else:
        raise ValueError(strategy)

    return signal_metrics(
        df,
        entry,
        exit_signal=exit_signal,
        min_hold_days=min_hold_days,
        confirm_days=confirm_days,
        cooldown_days=0,
    )


def rows_for_stock(stock: Any, df: pd.DataFrame, basket: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    strategies = [
        "base_combo",
        "no_new_entries_in_down",
        "bull_delay_ma20",
        "bull_delay_ma55",
        "adaptive_ma20_no_down",
        "adaptive_ma55_no_down",
        "adaptive_shou_no_down",
        "bull_no_sell_until_ma20",
    ]
    for window, part in rolling_windows(df):
        if len(part) < 180:
            continue
        regime = align_regime(part, basket)
        bh = benchmark_buy_hold(part)
        wr = window_regime(regime)
        for strategy in strategies:
            result = strategy_result(part, regime, strategy)
            rows.append(
                {
                    "strategy": strategy,
                    "window": window,
                    "basket_regime": wr,
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
                    "bh_max_drawdown": bh["max_drawdown"],
                    "vs_bh": round(result["total_return"] - bh["total_return"], 2),
                }
            )
    return rows


def write_report(path: Path, overall: pd.DataFrame, by_regime: pd.DataFrame, by_segment: pd.DataFrame) -> None:
    lines = [
        "# Market Regime Filter Tests",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Basket bull definition: equal-weight AI basket index above MA60 and 60-day return > 20%.",
        "Basket down definition: index below MA60 and 60-day return < 0.",
        "",
        "## Overall Rolling Windows",
        "",
        "| strategy | samples | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in overall.to_dict("records"):
        lines.append(
            f"| {r['strategy']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_drawdown']:.2f}% | {r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## By Basket Regime",
            "",
            "| strategy | basket_regime | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in by_regime.to_dict("records"):
        lines.append(
            f"| {r['strategy']} | {r['basket_regime']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Best Strategy By Segment",
            "",
            "| segment | strategy | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    best_segments = by_segment.sort_values(["segment", "median_calmar", "median_return"], ascending=[True, False, False])
    best_segments = best_segments.groupby("segment", as_index=False).head(1)
    for r in best_segments.to_dict("records"):
        lines.append(
            f"| {r['segment']} | {r['strategy']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    stocks = [s for s in build_universe() if "ai_basket" in s.source]
    data: dict[str, pd.DataFrame] = {}
    failures: list[str] = []
    for stock in stocks:
        try:
            df = fetch_daily_tencent(stock.code, count=500)
            if df.empty or len(df) < 300:
                raise RuntimeError("empty or insufficient data")
            data[stock.code] = df
        except Exception as exc:
            failures.append(f"{stock.code} {stock.name}: {exc}")

    basket = build_basket_index(data)
    rows: list[dict[str, Any]] = []
    by_code = {s.code: s for s in stocks}
    for code, df in data.items():
        rows.extend(rows_for_stock(by_code[code], df, basket))

    raw = pd.DataFrame(rows)
    overall = aggregate(raw, ["strategy"])
    by_regime = aggregate(raw, ["strategy", "basket_regime"])
    by_segment = aggregate(raw, ["strategy", "segment"])

    raw.to_csv(reports / "v1_market_regime_by_window_stock.csv", index=False)
    overall.to_csv(reports / "v1_market_regime_overall.csv", index=False)
    by_regime.to_csv(reports / "v1_market_regime_by_regime.csv", index=False)
    by_segment.to_csv(reports / "v1_market_regime_by_segment.csv", index=False)
    basket.to_csv(reports / "v1_ai_basket_index.csv", index=False)
    write_report(reports / "v1_market_regime_filters.md", overall, by_regime, by_segment)

    print(f"rows={len(raw)} stocks={len(data)} failures={len(failures)}")
    print(reports / "v1_market_regime_filters.md")
    if failures:
        print("\n".join(failures[:10]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
