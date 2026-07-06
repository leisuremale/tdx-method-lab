"""Check whether the combo strategy is mostly an AI bull-market artifact."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

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


CANDIDATES = [
    {
        "strategy": "candidate_low25_hold20_confirm4",
        "entry": "low_kdj_25",
        "min_hold_days": 20,
        "confirm_days": 4,
    },
    {
        "strategy": "candidate_tianma_hold20_confirm4",
        "entry": "tianma",
        "min_hold_days": 20,
        "confirm_days": 4,
    },
    {
        "strategy": "control_tianma_fixed20",
        "entry": "tianma",
        "fixed_hold_days": 20,
    },
]


def rolling_windows(df: pd.DataFrame, window: int = 250, step: int = 60) -> list[tuple[str, pd.DataFrame]]:
    out = []
    n = len(df)
    start = 0
    while start + window <= n:
        part = df.iloc[start : start + window].reset_index(drop=True)
        label = f"{pd.to_datetime(part['date'].iloc[0]).date()}_{pd.to_datetime(part['date'].iloc[-1]).date()}"
        out.append((label, part))
        start += step
    if out and pd.to_datetime(out[-1][1]["date"].iloc[-1]).date() != pd.to_datetime(df["date"].iloc[-1]).date():
        part = df.iloc[-window:].reset_index(drop=True)
        label = f"{pd.to_datetime(part['date'].iloc[0]).date()}_{pd.to_datetime(part['date'].iloc[-1]).date()}"
        out.append((label, part))
    return out


def bh_regime(bh_return: float) -> str:
    if bh_return >= 80:
        return "bull_80pct_plus"
    if bh_return >= 20:
        return "up_20_to_80pct"
    if bh_return >= 0:
        return "flat_0_to_20pct"
    return "down_negative"


def run_strategy(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    entry = sub["tian_ma"]
    if config["entry"] == "low_kdj_25":
        entry = cross_up(sub["az3"], sub["az4"]) & (sub["az3"] < 25)

    if "fixed_hold_days" in config:
        return signal_metrics(df, entry, hold_days=config["fixed_hold_days"])

    exit_signal = (~sub["hold_line"]) | main["trend_down"]
    return signal_metrics(
        df,
        entry,
        exit_signal=exit_signal,
        min_hold_days=config["min_hold_days"],
        confirm_days=config["confirm_days"],
        cooldown_days=0,
    )


def stock_window_rows(stock: Any, df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for window, part in rolling_windows(df):
        if len(part) < 180:
            continue
        bh = benchmark_buy_hold(part)
        regime = bh_regime(float(bh["total_return"]))
        for config in CANDIDATES:
            result = run_strategy(part, config)
            rows.append(
                {
                    "strategy": config["strategy"],
                    "window": window,
                    "regime": regime,
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


def write_report(
    path: Path,
    overall: pd.DataFrame,
    by_regime: pd.DataFrame,
    by_window: pd.DataFrame,
    by_segment: pd.DataFrame,
) -> None:
    lines = [
        "# Bull Market Bias Validation",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Universe: Feishu AI basket, common-account tradable, excluding 688.",
        "Method under test: `low_kdj_25 + min_hold=20 + exit=(hold_line gone OR trend_down) + confirm=4`.",
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
            "## By Buy-Hold Regime",
            "",
            "| strategy | regime | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in by_regime.to_dict("records"):
        lines.append(
            f"| {r['strategy']} | {r['regime']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Weak Windows For Candidate",
            "",
            "| window | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    candidate_windows = by_window[by_window["strategy"] == "candidate_low25_hold20_confirm4"].sort_values("median_calmar")
    for r in candidate_windows.to_dict("records"):
        lines.append(
            f"| {r['window']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Candidate By Segment",
            "",
            "| segment | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    candidate_segments = by_segment[by_segment["strategy"] == "candidate_low25_hold20_confirm4"]
    candidate_segments = candidate_segments.sort_values("median_calmar", ascending=False)
    for r in candidate_segments.to_dict("records"):
        lines.append(
            f"| {r['segment']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for stock in build_universe():
        if "ai_basket" not in stock.source:
            continue
        try:
            df = fetch_daily_tencent(stock.code, count=500)
            if df.empty or len(df) < 300:
                raise RuntimeError("empty or insufficient data")
            rows.extend(stock_window_rows(stock, df))
        except Exception as exc:
            failures.append(f"{stock.code} {stock.name}: {exc}")

    raw = pd.DataFrame(rows)
    overall = aggregate(raw, ["strategy"])
    by_regime = aggregate(raw, ["strategy", "regime"])
    by_window = aggregate(raw, ["strategy", "window"])
    by_segment = aggregate(raw, ["strategy", "segment"])

    raw.to_csv(reports / "v1_bull_bias_by_window_stock.csv", index=False)
    overall.to_csv(reports / "v1_bull_bias_overall.csv", index=False)
    by_regime.to_csv(reports / "v1_bull_bias_by_regime.csv", index=False)
    by_window.to_csv(reports / "v1_bull_bias_by_window.csv", index=False)
    by_segment.to_csv(reports / "v1_bull_bias_by_segment.csv", index=False)
    write_report(reports / "v1_bull_market_bias.md", overall, by_regime, by_window, by_segment)

    print(f"rows={len(raw)} stocks={raw['code'].nunique() if not raw.empty else 0} failures={len(failures)}")
    print(reports / "v1_bull_market_bias.md")
    if failures:
        print("\n".join(failures[:10]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
