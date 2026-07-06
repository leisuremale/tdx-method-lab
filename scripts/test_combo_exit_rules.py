"""Test hybrid exits: minimum hold window plus visual-line exit confirmation."""

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


def datasets(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    mid = len(df) // 2
    return [
        ("full", df.reset_index(drop=True)),
        ("first_half", df.iloc[:mid].reset_index(drop=True)),
        ("second_half", df.iloc[mid:].reset_index(drop=True)),
    ]


def exit_signals(sub: dict, main: dict) -> dict[str, Any]:
    hold_gone = ~sub["hold_line"]
    shou_gone = ~sub["shou_cang"]
    mu_gone = ~main["mu_ma"]
    trend_down = main["trend_down"]
    return {
        "hold_gone": hold_gone,
        "shou_gone": shou_gone,
        "hold_or_shou_gone": hold_gone | shou_gone,
        "hold_and_shou_gone": hold_gone & shou_gone,
        "shou_or_trend_down": shou_gone | trend_down,
        "hold_or_trend_down": hold_gone | trend_down,
        "mu_or_shou_gone": mu_gone | shou_gone,
    }


def row(stock: Any, period: str, strategy: str, df: pd.DataFrame, result: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    bh = benchmark_buy_hold(df)
    return {
        "period": period,
        "strategy": strategy,
        "code": stock.code,
        "name": stock.name,
        "segment": stock.segment,
        **params,
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


def combo_rows(stock: Any, df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period, part in datasets(df):
        if len(part) < 120:
            continue
        sub = compute_xhsub(part)
        main = compute_xhmain(part)
        entries = {
            "tianma": sub["tian_ma"],
            "low_kdj_25": (sub["az3"] < 25) & (sub["az3"] > sub["az4"]),
        }
        exits = exit_signals(sub, main)

        for entry_name, entry_signal in entries.items():
            for exit_name, exit_signal in exits.items():
                for min_hold_days in [5, 10, 15, 20, 30]:
                    for confirm_days in [1, 2, 3, 4, 5]:
                        result = signal_metrics(
                            part,
                            entry_signal,
                            exit_signal=exit_signal,
                            min_hold_days=min_hold_days,
                            confirm_days=confirm_days,
                            cooldown_days=0,
                        )
                        rows.append(
                            row(
                                stock,
                                period,
                                f"{entry_name}__{exit_name}",
                                part,
                                result,
                                {
                                    "entry": entry_name,
                                    "exit": exit_name,
                                    "min_hold_days": min_hold_days,
                                    "confirm_days": confirm_days,
                                    "cooldown_days": 0,
                                },
                            )
                        )
    return rows


def stability_summary(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["strategy", "entry", "exit", "min_hold_days", "confirm_days", "cooldown_days"]
    rows = []
    for key, group in summary.groupby(keys, dropna=False):
        periods = {r["period"]: r for r in group.to_dict("records")}
        if not {"full", "first_half", "second_half"}.issubset(periods):
            continue
        full = periods["full"]
        first = periods["first_half"]
        second = periods["second_half"]
        row = dict(zip(keys, key))
        row.update(
            {
                "full_median_calmar": full["median_calmar"],
                "first_median_calmar": first["median_calmar"],
                "second_median_calmar": second["median_calmar"],
                "worst_half_calmar": min(first["median_calmar"], second["median_calmar"]),
                "full_median_return": full["median_return"],
                "first_median_return": first["median_return"],
                "second_median_return": second["median_return"],
                "full_trades": full["trades"],
                "full_win": full["weighted_win_rate"],
                "full_positive": full["positive_stocks"],
                "full_beat_bh": full["beat_bh_stocks"],
                "full_median_vs_bh": full["median_vs_bh"],
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["worst_half_calmar", "full_median_calmar", "full_median_return"],
        ascending=[False, False, False],
    )


def write_report(path: Path, stable: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = [
        "# V1 Combo Exit Tests",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Universe: Feishu AI basket, common-account tradable, excluding 688.",
        "",
        "Rule shape: entry signal -> minimum hold days -> exit only after visual-line condition persists for confirm days.",
        "",
        "## Robust Top 30",
        "",
        "| entry | exit | min_hold | confirm | full_calmar | first_calmar | second_calmar | worst_half | full_return | full_win | positive | beatBH | full_vsBH | trades |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in stable.head(30).to_dict("records"):
        lines.append(
            f"| {r['entry']} | {r['exit']} | {int(r['min_hold_days'])} | {int(r['confirm_days'])} | "
            f"{r['full_median_calmar']:.2f} | {r['first_median_calmar']:.2f} | {r['second_median_calmar']:.2f} | "
            f"{r['worst_half_calmar']:.2f} | {r['full_median_return']:.2f}% | {r['full_win']:.2f}% | "
            f"{int(r['full_positive'])} | {int(r['full_beat_bh'])} | {r['full_median_vs_bh']:.2f}% | {int(r['full_trades'])} |"
        )

    lines.extend(
        [
            "",
            "## Full Sample Top 30",
            "",
            "| entry | exit | min_hold | confirm | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    full = summary[summary["period"] == "full"].sort_values(["median_calmar", "median_return"], ascending=[False, False])
    for r in full.head(30).to_dict("records"):
        lines.append(
            f"| {r['entry']} | {r['exit']} | {int(r['min_hold_days'])} | {int(r['confirm_days'])} | {int(r['trades'])} | "
            f"{r['weighted_win_rate']:.2f}% | {int(r['positive_stocks'])} | {int(r['beat_bh_stocks'])} | "
            f"{r['median_return']:.2f}% | {r['median_drawdown']:.2f}% | {r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
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
            if df.empty or len(df) < 240:
                raise RuntimeError("empty or insufficient data")
            rows.extend(combo_rows(stock, df))
        except Exception as exc:
            failures.append(f"{stock.code} {stock.name}: {exc}")

    raw = pd.DataFrame(rows)
    group_cols = ["period", "strategy", "entry", "exit", "min_hold_days", "confirm_days", "cooldown_days"]
    summary = aggregate(raw, group_cols)
    stable = stability_summary(summary)

    raw.to_csv(reports / "v1_combo_exit_by_stock.csv", index=False)
    summary.to_csv(reports / "v1_combo_exit_summary.csv", index=False)
    stable.to_csv(reports / "v1_combo_exit_stability.csv", index=False)
    write_report(reports / "v1_combo_exit_tests.md", stable, summary)

    print(f"stocks={summary['stocks'].max() if not summary.empty else 0} failures={len(failures)}")
    print(reports / "v1_combo_exit_tests.md")
    if failures:
        print("\n".join(failures[:10]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
