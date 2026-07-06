"""Validate confirm_days robustness and visual-line exit rules."""

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

from compare_controls_and_tune import aggregate, signal_metrics
from export_signal_events import build_universe
from tdx_lab.backtest import benchmark_buy_hold
from tdx_lab.data import fetch_daily_tencent
from tdx_lab.indicators import compute_xhmain, compute_xhsub


def _result_row(stock: Any, period: str, strategy: str, df: pd.DataFrame, result: dict[str, Any]) -> dict[str, Any]:
    bh = benchmark_buy_hold(df)
    return {
        "period": period,
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


def _datasets(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    mid = len(df) // 2
    return [
        ("full", df.reset_index(drop=True)),
        ("first_half", df.iloc[:mid].reset_index(drop=True)),
        ("second_half", df.iloc[mid:].reset_index(drop=True)),
    ]


def _exit_signals(sub: dict, main: dict) -> dict[str, Any]:
    return {
        "exit_hold_line_disappear": ~sub["hold_line"],
        "exit_shou_cang_disappear": ~sub["shou_cang"],
        "exit_mu_ma_disappear": ~main["mu_ma"],
        "exit_cao_pan_disappear": ~main["cao_pan"],
        "exit_trend_down": main["trend_down"],
        "exit_hold_or_trend_down": (~sub["hold_line"]) | main["trend_down"],
        "exit_mu_ma_or_hold": (~main["mu_ma"]) | (~sub["hold_line"]),
        "exit_cao_pan_or_hold": (~main["cao_pan"]) | (~sub["hold_line"]),
        "exit_shou_cang_or_hold": (~sub["shou_cang"]) | (~sub["hold_line"]),
    }


def visual_exit_rows(stock: Any, df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for period, part in _datasets(df):
        if len(part) < 120:
            continue
        sub = compute_xhsub(part)
        main = compute_xhmain(part)
        for strategy, exit_signal in _exit_signals(sub, main).items():
            result = signal_metrics(
                part,
                sub["tian_ma"],
                exit_signal=exit_signal,
                min_hold_days=3,
                confirm_days=2,
                cooldown_days=5,
            )
            rows.append(_result_row(stock, period, strategy, part, result))
    return rows


def confirm_validation_rows(stock: Any, df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for period, part in _datasets(df):
        if len(part) < 120:
            continue
        sub = compute_xhsub(part)
        main = compute_xhmain(part)
        exit_signal = (~sub["hold_line"]) | main["trend_down"]
        for confirm_days in [1, 2, 3, 4, 5]:
            for cooldown_days in [0, 5]:
                result = signal_metrics(
                    part,
                    sub["tian_ma"],
                    exit_signal=exit_signal,
                    min_hold_days=3,
                    confirm_days=confirm_days,
                    cooldown_days=cooldown_days,
                )
                row = _result_row(
                    stock,
                    period,
                    f"confirm_{confirm_days}_cooldown_{cooldown_days}",
                    part,
                    result,
                )
                row["confirm_days"] = confirm_days
                row["cooldown_days"] = cooldown_days
                rows.append(row)
    return rows


def write_report(path: Path, confirm: pd.DataFrame, visual: pd.DataFrame) -> None:
    lines = [
        "# Confirm Robustness And Visual Exit Tests",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Universe: Feishu AI basket, common-account tradable, excluding 688.",
        "",
        "## Confirm Days Robustness",
        "",
        "Read this as an overfit check: `confirm_days=3` should remain competitive in first-half and second-half slices, not only full sample.",
        "",
        "| period | confirm | cooldown | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    confirm_sorted = confirm.sort_values(["period", "median_calmar", "median_return"], ascending=[True, False, False])
    for row in confirm_sorted.to_dict("records"):
        lines.append(
            f"| {row['period']} | {int(row['confirm_days'])} | {int(row['cooldown_days'])} | {row['trades']} | "
            f"{row['weighted_win_rate']:.2f}% | {row['positive_stocks']} | {row['beat_bh_stocks']} | "
            f"{row['median_return']:.2f}% | {row['median_drawdown']:.2f}% | {row['median_calmar']:.2f} | {row['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Visual Exit Rules",
            "",
            "| period | exit_rule | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    visual_sorted = visual.sort_values(["period", "median_calmar", "median_return"], ascending=[True, False, False])
    for row in visual_sorted.to_dict("records"):
        lines.append(
            f"| {row['period']} | {row['strategy']} | {row['trades']} | {row['weighted_win_rate']:.2f}% | "
            f"{row['positive_stocks']} | {row['beat_bh_stocks']} | {row['median_return']:.2f}% | "
            f"{row['median_drawdown']:.2f}% | {row['median_calmar']:.2f} | {row['median_vs_bh']:.2f}% |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    confirm_rows: list[dict[str, Any]] = []
    visual_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for stock in build_universe():
        if "ai_basket" not in stock.source:
            continue
        try:
            df = fetch_daily_tencent(stock.code, count=500)
            if df.empty or len(df) < 240:
                raise RuntimeError("empty or insufficient data")
            confirm_rows.extend(confirm_validation_rows(stock, df))
            visual_rows.extend(visual_exit_rows(stock, df))
        except Exception as exc:
            failures.append(f"{stock.code} {stock.name}: {exc}")

    confirm_raw = pd.DataFrame(confirm_rows)
    visual_raw = pd.DataFrame(visual_rows)
    confirm_summary = aggregate(confirm_raw, ["period", "confirm_days", "cooldown_days"])
    visual_summary = aggregate(visual_raw, ["period", "strategy"])

    confirm_raw.to_csv(reports / "v1_confirm_validation_by_stock.csv", index=False)
    confirm_summary.to_csv(reports / "v1_confirm_validation_summary.csv", index=False)
    visual_raw.to_csv(reports / "v1_visual_exit_by_stock.csv", index=False)
    visual_summary.to_csv(reports / "v1_visual_exit_summary.csv", index=False)
    write_report(reports / "v1_confirm_visual_exit.md", confirm_summary, visual_summary)

    print(f"stocks={confirm_summary['stocks'].max() if not confirm_summary.empty else 0} failures={len(failures)}")
    print(reports / "v1_confirm_visual_exit.md")
    if failures:
        print("\n".join(failures[:10]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
