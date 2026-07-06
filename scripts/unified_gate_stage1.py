# -*- coding: utf-8 -*-
"""统一证伪关 Stage-1：预注册组合全网格 × 400只无偏差池 × 发现期 2021-2024。

诚实声明：本阶段就是系统性挖掘，其产出仅用于给 Stage-2 提供候选；
一切结论只能来自 Stage-2 的四关（随机对照/留出期/邻域/切片）。
网格定义即预注册记录，运行时 dump 到 reports/gate_grid_registry.json。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))

import numpy as np
import pandas as pd
from tdx_lab.event_engine import entry_from_event_confirm, simulate_events
from tdx_lab.indicators import compute_xhmain, compute_xhsub, compute_xhwater, sma_tdx

CACHE = LAB / "data" / "ohlcv_cache"
REPORTS = LAB / "reports"
DISCOVERY_END = "2024-12-31"
COST = 0.0013
CONFIRM_DAYS = 2
COOLDOWN = 5

EVENTS = ["tianma20", "tianma25", "trend_up", "var11", "strong_rev", "caopan_x"]
CONFIRMS = ["none", "ma20_w10", "ma20_w15", "muma_w10", "trendst_w10"]
EXITS = ["guanbian_dn", "trend_dn", "v1_tp_or_td", "water_slope", "nday_low10",
         "hold20", "zhz_break"]
MIN_HOLDS = [0, 20]
FILTERS = ["none", "mkt_ma60"]


def load_index_ma60() -> pd.Series:
    """沪深300 日线 close>MA60 的布尔序列（date 索引），本地缓存。"""
    path = LAB / "data" / "index_000300.csv"
    if not path.exists():
        import baostock as bs
        bs.login()
        r = bs.query_history_k_data_plus("sh.000300", "date,close",
                                         start_date="2020-09-01", end_date="2026-07-04",
                                         frequency="d", adjustflag="3")
        rows = []
        while r.error_code == "0" and r.next():
            rows.append(r.get_row_data())
        bs.logout()
        path.write_text("date,close\n" + "\n".join(",".join(x) for x in rows),
                        encoding="utf-8")
    df = pd.read_csv(path, parse_dates=["date"], index_col="date").astype(float)
    ma60 = df["close"].rolling(60).mean()
    return (df["close"] > ma60)


def stock_signals(df: pd.DataFrame) -> dict:
    """一只股票的全部预计算信号数组。"""
    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    water = compute_xhwater(df)
    c = df["close"].values
    n = len(c)

    az3, az4 = sub["az3"], sub["az4"]
    cross = np.zeros(n, bool)
    cross[1:] = (az3[1:] > az4[1:]) & (az3[:-1] <= az4[:-1])
    ma20 = pd.Series(c).rolling(20).mean().values
    llv10 = pd.Series(c).rolling(10).min().shift(1).values

    caopan = main["cao_pan"]
    caopan_x = np.zeros(n, bool)
    caopan_x[1:] = caopan[1:] & ~caopan[:-1]

    events = {
        "tianma20": cross & (az3 < 20),
        "tianma25": cross & (az3 < 25),
        "trend_up": main["trend_up"].astype(bool),
        "var11": main["var11"].astype(bool),
        "strong_rev": main["strong_reversal"].astype(bool),
        "caopan_x": caopan_x,
    }
    confirms = {
        "ma20": c > ma20,
        "muma": main["mu_ma"].astype(bool),
        "trendst": np.nan_to_num(main["cxhzb"]) >= np.nan_to_num(main["gzz"]),
    }
    exits = {
        "guanbian_dn": ~sub["hold_line"],
        "trend_dn": main["trend_down"].astype(bool),
        "v1_tp_or_td": (~sub["hold_line"]) | main["trend_down"].astype(bool),
        "water_slope": np.nan_to_num(water["water_slope_3"]) < 0,
        "nday_low10": c < np.nan_to_num(llv10, nan=-np.inf),
        "hold20": np.zeros(n, bool),          # 纯 max_hold=20 退出
        "zhz_break": np.zeros(n, bool),
    }
    zhz = sub["zhz"]
    zb = np.zeros(n, bool)
    zb[1:] = (zhz[1:] < 0) & (zhz[:-1] >= 0)
    exits["zhz_break"] = zb
    return {"events": events, "confirms": confirms, "exits": exits}


def build_entry(sig: dict, event: str, confirm: str) -> np.ndarray:
    ev = sig["events"][event]
    if confirm == "none":
        return ev
    name, w = confirm.rsplit("_w", 1)
    return entry_from_event_confirm(ev, sig["confirms"][name], int(w))


def portfolio_metrics(curves: list, index: pd.DatetimeIndex, end: str) -> dict:
    df = pd.concat(curves, axis=1).sort_index().ffill().fillna(1.0)
    port = df.mean(axis=1).loc[:end]
    d = port.pct_change().fillna(0.0)
    n = len(port)
    cagr = port.iloc[-1] ** (252 / n) - 1 if n else 0.0
    peak = port.cummax()
    maxdd = float((port / peak - 1).min())
    calmar = cagr / abs(maxdd) if maxdd < 0 else (float("inf") if cagr > 0 else 0.0)
    yearly = {str(y): round(float(g.iloc[-1] / g.iloc[0] - 1) * 100, 1)
              for y, g in port.groupby(port.index.year)}
    return {"cagr": round(float(cagr) * 100, 2), "maxdd": round(maxdd * 100, 2),
            "calmar": round(float(calmar), 3), "by_year": yearly}


def main() -> int:
    files = sorted(CACHE.glob("*.csv"))
    print(f"universe files: {len(files)}")
    mkt_ok = load_index_ma60()

    stocks = []
    for f in files:
        df = pd.read_csv(f, parse_dates=["date"]).astype(
            {"open": float, "high": float, "low": float, "close": float, "volume": float})
        if len(df) < 120:
            continue
        sig = stock_signals(df)
        mkt = mkt_ok.reindex(pd.DatetimeIndex(df["date"])).fillna(False).values
        stocks.append({"code": f.stem.split(".")[1], "df": df, "sig": sig, "mkt": mkt})
    print(f"prepared {len(stocks)} stocks")

    registry = {"events": EVENTS, "confirms": CONFIRMS, "exits": EXITS,
                "min_holds": MIN_HOLDS, "filters": FILTERS,
                "discovery_end": DISCOVERY_END, "cost": COST,
                "confirm_days": CONFIRM_DAYS, "cooldown": COOLDOWN,
                "execution": "T+1 next open; limit-up blocks entry; limit-down defers exit"}
    (REPORTS / "gate_grid_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = []
    total = len(EVENTS) * len(CONFIRMS) * len(EXITS) * len(MIN_HOLDS) * len(FILTERS)
    done = 0
    for event in EVENTS:
        for confirm in CONFIRMS:
            for exit_name in EXITS:
                for min_hold in MIN_HOLDS:
                    for filt in FILTERS:
                        curves, n_trades, wins, blocked = [], 0, 0, 0
                        for s in stocks:
                            entry = build_entry(s["sig"], event, confirm)
                            if filt == "mkt_ma60":
                                entry = entry & s["mkt"]
                            r = simulate_events(
                                s["df"]["open"].values, s["df"]["high"].values,
                                s["df"]["low"].values, s["df"]["close"].values,
                                entry, s["sig"]["exits"][exit_name], code=s["code"],
                                cost=COST, min_hold=min_hold,
                                max_hold=20 if exit_name == "hold20" else None,
                                confirm_days=CONFIRM_DAYS, cooldown=COOLDOWN)
                            curves.append(pd.Series(r["equity"],
                                                    index=pd.DatetimeIndex(s["df"]["date"])))
                            trades = [t for t in r["trades"]
                                      if str(s["df"]["date"].iloc[t["exit_idx"]].date()) <= DISCOVERY_END]
                            n_trades += len(trades)
                            wins += sum(1 for t in trades if t["return_pct"] > 0)
                            blocked += r["blocked_entries"]
                        m = portfolio_metrics(curves, None, DISCOVERY_END)
                        rows.append({"event": event, "confirm": confirm, "exit": exit_name,
                                     "min_hold": min_hold, "filter": filt,
                                     "n_trades": n_trades,
                                     "win_rate": round(wins / n_trades * 100, 1) if n_trades else 0,
                                     **{k: m[k] for k in ("cagr", "maxdd", "calmar")},
                                     "by_year": json.dumps(m["by_year"])})
                        done += 1
                        if done % 40 == 0:
                            print(f"  {done}/{total}", flush=True)

    out = pd.DataFrame(rows).sort_values("calmar", ascending=False)
    out.to_csv(REPORTS / "gate_stage1_grid.csv", index=False, encoding="utf-8-sig")
    print("\nTop 15 by discovery-period Calmar (仅为 Stage-2 候选，非结论):")
    print(out.head(15).drop(columns=["by_year"]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
