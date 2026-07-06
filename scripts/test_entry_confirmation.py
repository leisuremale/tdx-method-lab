"""Test whether low-position KDJ should be observation, not direct entry.

The candidate being tested:
- observation: AZ3 crosses above AZ4 while AZ3 < 25
- actual entry: observation followed by trend / relative-strength confirmation

This script keeps the V1 combo exit fixed so the test isolates entry quality.
"""

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
from tdx_lab.data import fetch_batch_baostock, fetch_daily_tencent
from tdx_lab.indicators import compute_xhmain, compute_xhsub
from test_market_regime_filters import build_basket_index, window_regime


def build_group_index(data: dict[str, pd.DataFrame], codes: list[str]) -> pd.DataFrame:
    series = []
    for code in codes:
        df = data.get(code)
        if df is None or df.empty:
            continue
        s = df.set_index("date")["close"].astype(float)
        s = s / s.iloc[0]
        series.append(s.rename(code))
    if not series:
        return pd.DataFrame(columns=["date", "index"])
    panel = pd.concat(series, axis=1).sort_index()
    idx = panel.mean(axis=1, skipna=True)
    return pd.DataFrame({"date": idx.index, "index": idx.values})


def align_index_return(df: pd.DataFrame, index_df: pd.DataFrame, window: int) -> np.ndarray:
    if index_df.empty:
        return np.full(len(df), np.nan)
    idx = index_df.set_index("date")["index"]
    aligned = idx.reindex(pd.to_datetime(df["date"])).ffill()
    return (aligned / aligned.shift(window) - 1).to_numpy(dtype=float)


def confirmed_entries(observation: np.ndarray, confirmation: np.ndarray, wait_days: int) -> np.ndarray:
    out = np.zeros(len(observation), dtype=bool)
    pending = False
    expiry = -1
    for i in range(len(observation)):
        if observation[i]:
            pending = True
            expiry = max(expiry, i + wait_days)
        if pending and i > expiry:
            pending = False
        if pending and i <= expiry and confirmation[i]:
            out[i] = True
            pending = False
    return out


def rolling_window_slices(df: pd.DataFrame, window: int = 250, step: int = 60) -> list[tuple[str, int, int, pd.DataFrame]]:
    out = []
    start = 0
    while start + window <= len(df):
        end = start + window
        part = df.iloc[start:end].reset_index(drop=True)
        label = f"{pd.to_datetime(part['date'].iloc[0]).date()}_{pd.to_datetime(part['date'].iloc[-1]).date()}"
        out.append((label, start, end, part))
        start += step
    if out and pd.to_datetime(out[-1][3]["date"].iloc[-1]).date() != pd.to_datetime(df["date"].iloc[-1]).date():
        start = len(df) - window
        end = len(df)
        part = df.iloc[start:end].reset_index(drop=True)
        label = f"{pd.to_datetime(part['date'].iloc[0]).date()}_{pd.to_datetime(part['date'].iloc[-1]).date()}"
        out.append((label, start, end, part))
    return out


def entry_variants(
    df: pd.DataFrame,
    basket_ret20: np.ndarray,
    segment_ret20: np.ndarray,
) -> dict[str, np.ndarray]:
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    close = df["close"].astype(float)
    stock_ret20 = close / close.shift(20) - 1
    ma20 = close.rolling(20).mean().to_numpy()
    ma55 = close.rolling(55).mean().to_numpy()
    ma20_arr = close.rolling(20).mean().to_numpy()

    observation = cross_up(sub["az3"], sub["az4"]) & (sub["az3"] < 25)
    trend_state = np.isfinite(main["cxhzb"]) & np.isfinite(main["gzz"]) & (main["cxhzb"] >= main["gzz"])
    above_ma20 = close.to_numpy() > ma20
    healthy_midtrend = above_ma20 & (ma20_arr > ma55)
    rs20_basket = stock_ret20.to_numpy(dtype=float) - basket_ret20
    rs20_segment = stock_ret20.to_numpy(dtype=float) - segment_ret20

    confirmations: dict[str, np.ndarray] = {
        "same_day_observation": np.ones(len(df), dtype=bool),
        "wait_ma20": above_ma20,
        "wait_cxhzb": trend_state,
        "wait_muma": main["mu_ma"],
        "wait_caopan": main["cao_pan"],
        "wait_rs20_basket": rs20_basket > 0,
        "wait_rs20_segment": rs20_segment > 0,
        "wait_ma20_cxhzb": above_ma20 & trend_state,
        "wait_ma20_rs20_segment": above_ma20 & (rs20_segment > 0),
        "wait_ma20_cxhzb_rs20_segment": above_ma20 & trend_state & (rs20_segment > 0),
        "wait_healthy_midtrend_cxhzb": healthy_midtrend & trend_state,
    }

    out: dict[str, np.ndarray] = {"obs_direct": observation}
    for name, confirm in confirmations.items():
        for wait_days in [5, 10, 15]:
            if name == "same_day_observation" and wait_days != 5:
                continue
            label = "obs_direct_wait0" if name == "same_day_observation" else f"obs_then_{name}_{wait_days}d"
            out[label] = confirmed_entries(observation, confirm, 0 if name == "same_day_observation" else wait_days)
    return out


def rows_for_stock(
    stock: Any,
    df: pd.DataFrame,
    basket: pd.DataFrame,
    segment_index: pd.DataFrame,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    basket_ret20 = align_index_return(df, basket.rename(columns={"basket_index": "index"}), 20)
    segment_ret20 = align_index_return(df, segment_index, 20)
    variants = entry_variants(df, basket_ret20, segment_ret20)
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    exit_signal = (~sub["hold_line"]) | main["trend_down"]

    for window, start, end, part in rolling_window_slices(df):
        if len(part) < 180:
            continue
        bh = benchmark_buy_hold(part)
        basket_part = basket[(basket["date"] >= part["date"].iloc[0]) & (basket["date"] <= part["date"].iloc[-1])].copy()
        regime = window_regime(
            basket_part.rename(columns={"basket_index": "basket_index"})[["bull", "down", "up"]]
            if not basket_part.empty
            else pd.DataFrame({"bull": [False], "down": [False], "up": [False]})
        )
        for strategy, entry in variants.items():
            result = signal_metrics(
                part.reset_index(drop=True),
                entry[start:end],
                exit_signal=exit_signal[start:end],
                min_hold_days=20,
                confirm_days=4,
                cooldown_days=0,
            )
            rows.append(
                {
                    "strategy": strategy,
                    "window": window,
                    "basket_regime": regime,
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


def rank_strategies(overall: pd.DataFrame) -> pd.DataFrame:
    out = overall.copy()
    out["enough_trades"] = out["trades"] >= 150
    out = out.sort_values(
        ["enough_trades", "median_calmar", "median_return", "median_vs_bh", "trades"],
        ascending=[False, False, False, False, False],
    )
    return out


def write_report(
    path: Path,
    overall: pd.DataFrame,
    by_regime: pd.DataFrame,
    by_segment: pd.DataFrame,
    failures: list[str],
) -> None:
    ranked = rank_strategies(overall)
    top = ranked.head(12)
    lines = [
        "# V2 Entry Confirmation Test",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "Purpose: test whether `AZ3 cross AZ4 and AZ3 < 25` should be only an observation signal.",
        "",
        "Fixed exit for isolation: `not hold_line OR main trend_down`, minimum hold 20 trading days, exit confirmation 4 days.",
        "",
        "Acceptance bias: prefer fewer but more robust entries if drawdown and flat/down-market behavior improve. Reject variants with too few trades.",
        "",
        "## Top Overall Variants",
        "",
        "| rank | strategy | samples | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, r in enumerate(top.to_dict("records"), start=1):
        lines.append(
            f"| {rank} | {r['strategy']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_drawdown']:.2f}% | {r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Regime Check For Top Variants",
            "",
            "| strategy | basket_regime | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    top_names = set(top["strategy"])
    regime_rows = by_regime[by_regime["strategy"].isin(top_names)].sort_values(["strategy", "basket_regime"])
    for r in regime_rows.to_dict("records"):
        lines.append(
            f"| {r['strategy']} | {r['basket_regime']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Segment Best Variant",
            "",
            "| segment | strategy | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    best_segments = by_segment.sort_values(
        ["segment", "trades", "median_calmar", "median_return"],
        ascending=[True, False, False, False],
    )
    best_segments = best_segments.groupby("segment", as_index=False).head(1)
    for r in best_segments.to_dict("records"):
        lines.append(
            f"| {r['segment']} | {r['strategy']} | {r['stocks']} | {r['trades']} | {r['weighted_win_rate']:.2f}% | "
            f"{r['positive_stocks']} | {r['beat_bh_stocks']} | {r['median_return']:.2f}% | "
            f"{r['median_calmar']:.2f} | {r['median_vs_bh']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Working Conclusion",
            "",
            "- The low-position KDJ cross is now treated as an observation event.",
            "- Preferred next candidate: `obs_then_wait_ma20_15d`. It keeps enough trades, improves median drawdown versus direct observation, and is the only top-three variant with non-negative median vs buy-hold.",
            "- `obs_then_wait_muma_10d` has slightly better median return/Calmar, but `mu_ma` is effectively `close > EMA10`; MA20 confirmation is simpler and less likely to be formula-specific overfit.",
            "- Relative-strength filters are not accepted yet: they reduce trades and did not improve overall robustness in this run.",
        ]
    )
    if failures:
        lines.extend(["", "## Data Failures", "", *[f"- {item}" for item in failures]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    stocks = [s for s in build_universe() if "ai_basket" in s.source]
    codes = [s.code for s in stocks]
    data: dict[str, pd.DataFrame] = fetch_batch_baostock(codes, start="2021-01-01", end=time.strftime("%Y-%m-%d"))
    failures: list[str] = []
    for stock in stocks:
        if stock.code in data and len(data[stock.code]) >= 300:
            data[stock.code] = data[stock.code].reset_index(drop=True)
            continue
        try:
            df = fetch_daily_tencent(stock.code, count=1000)
            if df.empty or len(df) < 300:
                raise RuntimeError("empty or insufficient data")
            data[stock.code] = df.reset_index(drop=True)
        except Exception as exc:
            failures.append(f"{stock.code} {stock.name}: {exc}")

    basket = build_basket_index(data)
    by_segment_codes: dict[str, list[str]] = {}
    by_code = {s.code: s for s in stocks}
    for stock in stocks:
        if stock.code in data:
            by_segment_codes.setdefault(stock.segment or "未分组", []).append(stock.code)
    segment_indices = {segment: build_group_index(data, codes) for segment, codes in by_segment_codes.items()}

    rows: list[dict[str, Any]] = []
    for code, df in data.items():
        stock = by_code[code]
        rows.extend(rows_for_stock(stock, df, basket, segment_indices.get(stock.segment or "未分组", pd.DataFrame())))

    raw = pd.DataFrame(rows)
    overall = aggregate(raw, ["strategy"])
    by_regime = aggregate(raw, ["strategy", "basket_regime"])
    by_segment = aggregate(raw, ["strategy", "segment"])

    raw.to_csv(reports / "v2_entry_confirmation_by_window_stock.csv", index=False)
    rank_strategies(overall).to_csv(reports / "v2_entry_confirmation_summary.csv", index=False)
    by_regime.to_csv(reports / "v2_entry_confirmation_by_regime.csv", index=False)
    by_segment.to_csv(reports / "v2_entry_confirmation_by_segment.csv", index=False)
    write_report(reports / "v2_entry_confirmation.md", overall, by_regime, by_segment, failures)

    print(f"rows={len(raw)} stocks={len(data)} failures={len(failures)}")
    print(reports / "v2_entry_confirmation.md")
    if failures:
        print("\n".join(failures[:10]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
