"""Backtest the V1 signal method on the Feishu AI universe.

Universe matches export_signal_events.py:
- Feishu AI basket view.
- Exclude STAR Market codes starting with 688.
- Keep only rows where 普通账户可交易 is true.

Primary method:
- Entry: tian_ma_only
- Exit: take_profit_or_trend_down
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in [SRC, SCRIPTS]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from export_signal_events import build_universe
from tdx_lab.backtest import benchmark_buy_hold, simulate
from tdx_lab.data import fetch_daily_tencent
from tdx_lab.indicators import compute_xhmain, compute_xhsub


def analyze_stock(stock: Any, count: int, entry_rule: str, exit_rule: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    df = fetch_daily_tencent(stock.code, count=count)
    if df.empty or len(df) < 120:
        raise RuntimeError("empty or insufficient Tencent daily data")

    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    result = simulate(df, sub, main, entry_rules=entry_rule, exit_rules=exit_rule)
    bh = benchmark_buy_hold(df)

    row = {
        "code": stock.code,
        "name": stock.name,
        "source": stock.source,
        "segment": stock.segment,
        "layer": stock.layer,
        "start_date": pd.to_datetime(df["date"].iloc[34]).date().isoformat(),
        "end_date": pd.to_datetime(df["date"].iloc[-1]).date().isoformat(),
        "last_close": round(float(df["close"].iloc[-1]), 2),
        "entry_rule": entry_rule,
        "exit_rule": exit_rule,
        "n_trades": result["n_trades"],
        "win_rate": result["win_rate"],
        "total_return": result["total_return"],
        "max_drawdown": result["max_drawdown"],
        "calmar": result["calmar"],
        "avg_return": result["avg_return"],
        "avg_hold_days": result["avg_hold_days"],
        "bh_return": bh["total_return"],
        "vs_bh": round(result["total_return"] - bh["total_return"], 2),
        "entry_signals": result["entry_signals"],
        "exit_signals": result["exit_signals"],
    }

    trades = []
    for trade in result["trades"]:
        trades.append(
            {
                "code": stock.code,
                "name": stock.name,
                "segment": stock.segment,
                **trade,
            }
        )
    return row, trades


def _fmt_pct(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return f"{value:.2f}%"


def write_report(path: Path, summary: pd.DataFrame, failures: list[dict[str, str]], entry_rule: str, exit_rule: str) -> None:
    active = summary[summary["n_trades"] > 0]
    total_trades = int(summary["n_trades"].sum()) if not summary.empty else 0
    weighted_win = (
        float((summary["win_rate"] * summary["n_trades"]).sum() / total_trades)
        if total_trades
        else 0.0
    )
    profitable_stocks = int((summary["total_return"] > 0).sum()) if not summary.empty else 0
    beat_bh = int((summary["vs_bh"] > 0).sum()) if not summary.empty else 0

    lines = [
        "# V1 Backtest Summary",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Universe: Feishu AI basket view, excluding 688 and rows where `普通账户可交易` is not true.",
        f"Entry: `{entry_rule}`",
        f"Exit: `{exit_rule}`",
        "Cost: 0.13% per side",
        "",
        "## Verdict Metrics",
        "",
        f"- Stocks analyzed: {len(summary)}",
        f"- Stocks with closed trades: {len(active)}",
        f"- Closed trades: {total_trades}",
        f"- Trade-weighted win rate: {_fmt_pct(weighted_win)}",
        f"- Positive strategy return stocks: {profitable_stocks}/{len(summary)}",
        f"- Beat buy-and-hold stocks: {beat_bh}/{len(summary)}",
        f"- Median strategy return: {_fmt_pct(float(summary['total_return'].median()) if not summary.empty else 0.0)}",
        f"- Median max drawdown: {_fmt_pct(float(summary['max_drawdown'].median()) if not summary.empty else 0.0)}",
        f"- Median Calmar: {float(summary['calmar'].median()) if not summary.empty else 0.0:.2f}",
        "",
        "## Top By Calmar",
        "",
        "| 代码 | 名称 | 细分环节 | 交易数 | 胜率 | 收益 | 最大回撤 | Calmar | 买入持有 | vsBH |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    top = summary.sort_values(["n_trades", "calmar", "total_return"], ascending=[False, False, False]).head(20)
    for row in top.to_dict("records"):
        lines.append(
            f"| {row['code']} | {row['name']} | {row['segment']} | {int(row['n_trades'])} | "
            f"{_fmt_pct(float(row['win_rate']))} | {_fmt_pct(float(row['total_return']))} | "
            f"{_fmt_pct(float(row['max_drawdown']))} | {float(row['calmar']):.2f} | "
            f"{_fmt_pct(float(row['bh_return']))} | {_fmt_pct(float(row['vs_bh']))} |"
        )

    lines.extend(
        [
            "",
            "## Segment Summary",
            "",
            "| 细分环节 | 股票数 | 交易数 | 加权胜率 | 中位收益 | 中位回撤 | 跑赢BH |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for segment, group in summary.groupby("segment", dropna=False):
        trades = int(group["n_trades"].sum())
        win = float((group["win_rate"] * group["n_trades"]).sum() / trades) if trades else 0.0
        lines.append(
            f"| {segment or '-'} | {len(group)} | {trades} | {_fmt_pct(win)} | "
            f"{_fmt_pct(float(group['total_return'].median()))} | "
            f"{_fmt_pct(float(group['max_drawdown'].median()))} | "
            f"{int((group['vs_bh'] > 0).sum())}/{len(group)} |"
        )

    if failures:
        lines.extend(["", "## Failures", "", "| 代码 | 名称 | 原因 |", "|---|---|---|"])
        for item in failures:
            lines.append(f"| {item['code']} | {item['name']} | {item['error']} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--entry-rule", default="tian_ma_only")
    parser.add_argument("--exit-rule", default="take_profit_or_trend_down")
    args = parser.parse_args()

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    rows: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for stock in build_universe():
        if "ai_basket" not in stock.source:
            continue
        try:
            row, stock_trades = analyze_stock(stock, args.count, args.entry_rule, args.exit_rule)
        except Exception as exc:
            failures.append({"code": stock.code, "name": stock.name, "error": str(exc)})
            continue
        rows.append(row)
        trades.extend(stock_trades)

    summary = pd.DataFrame(rows).sort_values(["n_trades", "calmar", "total_return"], ascending=[False, False, False])
    summary.to_csv(reports / "v1_backtest_summary.csv", index=False)
    pd.DataFrame(trades).to_csv(reports / "v1_backtest_trades.csv", index=False)
    write_report(reports / "v1_backtest_summary.md", summary, failures, args.entry_rule, args.exit_rule)

    total_trades = int(summary["n_trades"].sum()) if not summary.empty else 0
    weighted_win = float((summary["win_rate"] * summary["n_trades"]).sum() / total_trades) if total_trades else 0.0
    print(f"stocks={len(summary)} trades={total_trades} weighted_win_rate={weighted_win:.2f}% failures={len(failures)}")
    print(reports / "v1_backtest_summary.md")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
