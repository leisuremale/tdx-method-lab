"""Export TDX signal events and latest signal-date report.

Inputs:
- Three fixed sample stocks.
- Feishu Base AI universe view, filtered to common-account tradable stocks and
  excluding STAR Market codes that start with 688.

Outputs:
- reports/signal_events.csv
- reports/v1_signal_dates.md
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tdx_lab.data import fetch_daily_tencent
from tdx_lab.indicators import compute_xhmain, compute_xhsub, compute_xhwater
from tdx_lab.signals import daily_state, generate_signal_table

BASE_TOKEN = "Qbiibdo69aa2xosQaBLc2I26nQe"
TABLE_ID = "tblUFC3zWq0LeJHp"
VIEW_ID = "vewRI6naaf"

SAMPLE_STOCKS = [
    ("300308", "中际旭创"),
    ("002916", "深南电路"),
    ("300394", "天孚通信"),
]

FIELD_CODE = "股票代码"
FIELD_NAME = "股票名称"
FIELD_TRADEABLE = "普通账户可交易"
FIELD_SEGMENT = "细分环节"
FIELD_LAYER = "产业层级"

RECENT_SIGNAL_COLUMNS = [
    "tian_ma",
    "trend_up",
    "trend_down",
    "strong_reversal",
    "var11",
    "take_profit",
    "macd_positive_shrink",
    "macd_negative_break",
    "water_extreme",
    "water_turn",
]


@dataclass
class Stock:
    code: str
    name: str
    source: str
    segment: str = ""
    layer: str = ""


def _lark_cli() -> list[str]:
    cli = shutil.which("lark-cli")
    if cli:
        return [cli]

    bundled = Path.home() / ".openclaw/tools/node-v22.22.0/bin/lark-cli"
    if bundled.exists():
        return [str(bundled)]

    raise RuntimeError("lark-cli not found")


def _run_lark(args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("OPENCLAW_HOME", str(Path.home() / ".openclaw"))
    env["PATH"] = f"{Path.home()}/.openclaw/tools/node-v22.22.0/bin:" + env.get("PATH", "")
    env["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
    env["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
    proc = subprocess.run(
        [*_lark_cli(), *args],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"lark-cli failed ({proc.returncode}): {' '.join(args)}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return json.loads(proc.stdout)


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " / ".join(str(item) for item in value if item is not None)
    return str(value).strip()


def load_feishu_ai_universe() -> list[Stock]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        payload = _run_lark(
            [
                "base",
                "+record-list",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                TABLE_ID,
                "--view-id",
                VIEW_ID,
                "--limit",
                "200",
                "--offset",
                str(offset),
                "--as",
                "bot",
                "--format",
                "json",
            ]
        )
        data = payload.get("data", {})
        fields = data.get("fields", [])
        batch = [dict(zip(fields, row)) for row in data.get("data", [])]
        rows.extend(batch)
        if not data.get("has_more"):
            break
        offset += len(batch)

    stocks: list[Stock] = []
    seen: set[str] = set()
    for row in rows:
        code = _cell_text(row.get(FIELD_CODE))
        if not code or code in seen:
            continue
        if code.startswith("688"):
            continue
        if row.get(FIELD_TRADEABLE) is not True:
            continue
        seen.add(code)
        stocks.append(
            Stock(
                code=code,
                name=_cell_text(row.get(FIELD_NAME)),
                source="ai_basket",
                segment=_cell_text(row.get(FIELD_SEGMENT)),
                layer=_cell_text(row.get(FIELD_LAYER)),
            )
        )
    return stocks


def build_universe() -> list[Stock]:
    by_code: dict[str, Stock] = {
        code: Stock(code=code, name=name, source="sample") for code, name in SAMPLE_STOCKS
    }
    for stock in load_feishu_ai_universe():
        if stock.code in by_code:
            existing = by_code[stock.code]
            existing.source = "sample;ai_basket"
            existing.segment = stock.segment
            existing.layer = stock.layer
            if stock.name:
                existing.name = stock.name
        else:
            by_code[stock.code] = stock
    return list(by_code.values())


def latest_date(events: pd.DataFrame, signal_name: str) -> str:
    if events.empty:
        return ""
    dates = events.loc[events["signal_name"] == signal_name, "date"]
    if dates.empty:
        return ""
    return pd.to_datetime(dates).max().date().isoformat()


def latest_signal(events: pd.DataFrame, signal_uses: set[str]) -> str:
    if events.empty:
        return ""
    subset = events[events["signal_use"].isin(signal_uses)].copy()
    if subset.empty:
        return ""
    subset["date"] = pd.to_datetime(subset["date"])
    row = subset.sort_values("date").iloc[-1]
    return f"{row['date'].date().isoformat()} {row['signal_name']}"


def analyze_stock(stock: Stock, count: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = fetch_daily_tencent(stock.code, count=count)
    if df.empty or len(df) < 120:
        raise RuntimeError("empty or insufficient Tencent daily data")

    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    water = compute_xhwater(df)
    events = generate_signal_table(df, sub, main, water)
    if not events.empty:
        events.insert(0, "code", stock.code)
        events.insert(1, "name", stock.name)
        events.insert(2, "source", stock.source)
        events.insert(3, "segment", stock.segment)
        events.insert(4, "layer", stock.layer)
        events["date"] = pd.to_datetime(events["date"]).dt.date.astype(str)

    state = daily_state(df, sub, main).iloc[-1]
    summary = {
        "code": stock.code,
        "name": stock.name,
        "source": stock.source,
        "segment": stock.segment,
        "layer": stock.layer,
        "last_date": pd.to_datetime(df["date"].iloc[-1]).date().isoformat(),
        "last_close": round(float(df["close"].iloc[-1]), 2),
        "current_state": "持股" if int(state["hold"]) else "止盈",
        "macd_state": state["macd_state"],
        "zhz": state["zhz"],
        "az3": state["az3"],
        "cxhzb_state": ">=GZZ" if int(state["cxhzb_above_gzz"]) else "<GZZ",
        "latest_entry_signal": latest_signal(events, {"入场候选"}),
        "latest_exit_signal": latest_signal(events, {"退出候选", "止盈观察", "强退出", "退出辅助"}),
    }
    for signal_name in RECENT_SIGNAL_COLUMNS:
        summary[f"last_{signal_name}"] = latest_date(events, signal_name)
    return events, summary


def write_signal_report(path: Path, summaries: list[dict[str, Any]], failures: list[dict[str, str]]) -> None:
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S %z")
    df = pd.DataFrame(summaries)
    ai_df = df[df["source"].str.contains("ai_basket", na=False)].copy()
    ai_df = ai_df.sort_values(["segment", "code"], na_position="last")

    lines = [
        "# V1 Signal Dates",
        "",
        f"Generated: {generated_at}",
        "",
        "Universe: Feishu AI basket view, excluding codes starting with 688 and rows where `普通账户可交易` is not true.",
        f"AI basket stocks analyzed: {len(ai_df)}",
        f"Samples included in CSV: {sum(df['source'].str.contains('sample', na=False))}",
        "",
        "## Latest State",
        "",
        "| 代码 | 名称 | 细分环节 | 最新交易日 | 收盘 | 当前状态 | MACD | CXHZB | 最近入场信号 | 最近退出/风险信号 | 天马 | 趋势转强 | 趋势转弱 | VAR11 |",
        "|---|---|---|---:|---:|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in ai_df.to_dict("records"):
        lines.append(
            "| {code} | {name} | {segment} | {last_date} | {last_close} | {current_state} | "
            "{macd_state} | {cxhzb_state} | {latest_entry_signal} | {latest_exit_signal} | "
            "{last_tian_ma} | {last_trend_up} | {last_trend_down} | {last_var11} |".format(**row)
        )

    if failures:
        lines.extend(["", "## Failures", "", "| 代码 | 名称 | 原因 |", "|---|---|---|"])
        for item in failures:
            lines.append(f"| {item['code']} | {item['name']} | {item['error']} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500, help="daily bars to fetch per stock")
    args = parser.parse_args()

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    universe = build_universe()
    all_events: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for stock in universe:
        try:
            events, summary = analyze_stock(stock, args.count)
        except Exception as exc:
            failures.append({"code": stock.code, "name": stock.name, "error": str(exc)})
            continue
        all_events.append(events)
        summaries.append(summary)

    signal_path = reports / "signal_events.csv"
    if all_events:
        pd.concat(all_events, ignore_index=True).to_csv(signal_path, index=False)
    else:
        pd.DataFrame().to_csv(signal_path, index=False)

    write_signal_report(reports / "v1_signal_dates.md", summaries, failures)

    print(f"universe={len(universe)} ok={len(summaries)} failed={len(failures)}")
    print(signal_path)
    print(reports / "v1_signal_dates.md")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
