"""Build an operational candidate from validated segment policies."""

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
import numpy as np

from test_entry_confirmation import confirmed_entries
from test_market_regime_filters import align_regime, build_basket_index
from tdx_lab.backtest import benchmark_buy_hold
from tdx_lab.data import fetch_daily_tencent
from tdx_lab.indicators import compute_xhmain, compute_xhsub
from tdx_lab.signals import daily_state


POLICY_BY_SEGMENT = {
    # segment: strategy from v1_market_regime_by_segment.csv
    "先进封装/封测": "adaptive_shou_no_down",
    "大模型/AI应用/AIGC": "base_combo",
    "液冷/散热": "bull_no_sell_until_ma20",
    "CPO": "bull_delay_ma20",
    "HBM": "adaptive_ma55_no_down",
    "交换机/网络设备": "bull_delay_ma20",
    "覆铜板CCL": "base_combo",
}

BLOCKED_SEGMENTS = {
    "算力芯片/GPU/CPU设计",
    "连接器",
    "高速铜缆/铜连接",
    "算力/IDC/算力租赁",
    "PCB",
    "AI服务器",
}


def v2_entry_signal(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    sub = compute_xhsub(df)
    close = df["close"].astype(float)
    observation = cross_up(sub["az3"], sub["az4"]) & (sub["az3"] < 25)
    confirmation = close.to_numpy() > close.rolling(20).mean().to_numpy()
    entry = confirmed_entries(observation, confirmation, wait_days=15)
    return pd.Series(entry), pd.Series(observation)


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


def policy_strategy_result(df: pd.DataFrame, regime: pd.DataFrame, strategy: str) -> dict[str, Any]:
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    close = df["close"].astype(float)
    ma20 = close.rolling(20).mean().to_numpy()
    ma55 = close.rolling(55).mean().to_numpy()

    entry = v2_entry_signal(df)[0].to_numpy(dtype=bool)
    base_exit = (~sub["hold_line"]) | main["trend_down"]
    bull = regime["bull"].to_numpy(dtype=bool)
    down = regime["down"].to_numpy(dtype=bool)

    exit_signal = base_exit
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
        min_hold_days=20,
        confirm_days=confirm_days,
        cooldown_days=0,
    )


def policy_rows(stock: Any, df: pd.DataFrame, basket: pd.DataFrame) -> list[dict[str, Any]]:
    strategy = POLICY_BY_SEGMENT.get(stock.segment)
    if not strategy:
        return []
    rows = []
    for window, part in rolling_windows(df):
        if len(part) < 180:
            continue
        regime = align_regime(part, basket)
        result = policy_strategy_result(part, regime, strategy)
        bh = benchmark_buy_hold(part)
        rows.append(
            {
                "strategy": "segment_policy_v2",
                "segment_policy": strategy,
                "window": window,
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


def latest_action(stock: Any, df: pd.DataFrame, basket: pd.DataFrame) -> dict[str, Any]:
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    state = daily_state(df, sub, main).iloc[-1]
    latest = df.iloc[-1]
    regime = align_regime(df, basket).iloc[-1]
    strategy = POLICY_BY_SEGMENT.get(stock.segment, "")
    blocked = stock.segment in BLOCKED_SEGMENTS or not strategy

    entry_series, observation_series = v2_entry_signal(df)
    entry_signal = bool(entry_series.iloc[-1])
    observation_signal = bool(observation_series.iloc[-1])
    base_exit = bool((not sub["hold_line"][-1]) or main["trend_down"][-1])
    close = df["close"].astype(float)
    ma20 = close.rolling(20).mean().to_numpy()
    ma55 = close.rolling(55).mean().to_numpy()
    bull = bool(regime.get("bull", False))
    down = bool(regime.get("down", False))
    policy_exit = base_exit
    if strategy == "bull_delay_ma20" and bull:
        policy_exit = bool(close.iloc[-1] < ma20[-1])
    elif strategy == "bull_no_sell_until_ma20" and bull:
        policy_exit = bool(close.iloc[-1] < ma20[-1])
    elif strategy == "adaptive_ma55_no_down" and bull:
        policy_exit = bool(close.iloc[-1] < ma55[-1])
    elif strategy == "adaptive_shou_no_down" and bull:
        policy_exit = bool(not sub["shou_cang"][-1])

    policy_blocks_entry = strategy in {"adaptive_ma55_no_down", "adaptive_shou_no_down"} and down
    action = "ignore"
    reason = "segment_blocked_or_unvalidated"
    if not blocked:
        action = "watch"
        reason = "validated_segment"
        if entry_signal and not policy_blocks_entry:
            action = "entry_candidate"
            reason = "low_kdj_25_observation_confirmed_ma20_15d"
        elif policy_exit:
            action = "exit_condition"
            reason = f"{strategy}_exit_condition"

    return {
        "code": stock.code,
        "name": stock.name,
        "segment": stock.segment,
        "policy": strategy,
        "date": pd.to_datetime(latest["date"]).date().isoformat(),
        "close": round(float(latest["close"]), 2),
        "action": action,
        "reason": reason,
        "current_state": "持股" if int(state["hold"]) else "止盈",
        "macd_state": state["macd_state"],
        "cxhzb_above_gzz": int(state["cxhzb_above_gzz"]),
        "observation_signal_today": int(observation_signal),
        "entry_signal_today": int(entry_signal),
        "base_exit_signal_today": int(base_exit),
        "policy_exit_signal_today": int(policy_exit),
        "basket_bull": int(bull),
        "basket_down": int(down),
    }


def write_report(path: Path, policy_summary: pd.DataFrame, actions: pd.DataFrame) -> None:
    lines = [
        "# Operational Trading System V2",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Objective: find a practical trading system, not a pretty backtest.",
        "",
        "## System Status",
        "",
        "Verdict: candidate system only. It is usable for watchlist and manual confirmation, not yet for automatic execution.",
        "",
        "Core rule:",
        "",
        "1. Trade only validated segments.",
        "2. Observation is low KDJ restart: AZ3 crosses above AZ4 while AZ3 < 25.",
        "3. Entry requires close > MA20 within 15 trading days after the observation.",
        "4. Minimum hold: 20 trading days.",
        "5. Exit uses the segment policy selected from rolling-window tests.",
        "6. All orders require manual confirmation.",
        "",
        "## Validated Segment Policies",
        "",
        "| segment | policy |",
        "|---|---|",
    ]
    for segment, policy in POLICY_BY_SEGMENT.items():
        lines.append(f"| {segment} | {policy} |")

    lines.extend(
        [
            "",
            "## Rolling Window Result For Segment Policy",
            "",
            "| samples | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    r = policy_summary.iloc[0]
    lines.append(
        f"| {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | {r['positive_stocks']} | "
        f"{r['beat_bh_stocks']} | {r['median_return']:.2f}% | {r['median_drawdown']:.2f}% | "
        f"{r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
    )

    lines.extend(
        [
            "",
            "## Current Action List",
            "",
            "| action | code | name | segment | policy | date | close | reason | state | basket_down |",
            "|---|---|---|---|---|---:|---:|---|---|---:|",
        ]
    )
    order = {"entry_candidate": 0, "exit_condition": 1, "watch": 2, "ignore": 3}
    actions = actions.assign(_rank=actions["action"].map(order).fillna(9)).sort_values(["_rank", "segment", "code"])
    for row in actions.to_dict("records"):
        lines.append(
            f"| {row['action']} | {row['code']} | {row['name']} | {row['segment']} | {row['policy']} | "
            f"{row['date']} | {row['close']} | {row['reason']} | {row['current_state']} | {row['basket_down']} |"
        )

    lines.extend(
        [
            "",
            "## Blocked Segments",
            "",
            "Do not trade V2 mechanically in these segments until a separate edge is found:",
            "",
        ]
    )
    for segment in sorted(BLOCKED_SEGMENTS):
        lines.append(f"- {segment}")
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
    by_code = {s.code: s for s in stocks}
    rows: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for code, df in data.items():
        stock = by_code[code]
        rows.extend(policy_rows(stock, df, basket))
        actions.append(latest_action(stock, df, basket))

    raw = pd.DataFrame(rows)
    actions_df = pd.DataFrame(actions)
    policy_summary = aggregate(raw, ["strategy"])
    raw.to_csv(reports / "v1_operational_policy_by_window_stock.csv", index=False)
    policy_summary.to_csv(reports / "v1_operational_policy_summary.csv", index=False)
    actions_df.to_csv(reports / "v1_current_action_list.csv", index=False)
    write_report(reports / "v1_operational_trading_system.md", policy_summary, actions_df)

    print(f"policy_samples={len(raw)} actions={len(actions_df)} failures={len(failures)}")
    print(reports / "v1_operational_trading_system.md")
    if failures:
        print("\n".join(failures[:10]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
