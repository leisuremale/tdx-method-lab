# -*- coding: utf-8 -*-
"""统一证伪关·宽网格扫描（Stage-1 加宽版）：指标调参 × 组合 × 过滤，预注册 12,096 格。

性能设计：worker 进程各自加载一次全部信号变体；组合聚合用 numpy 主日历
scatter+ffill（不用 pandas per-combo）；4 进程并行；每 200 格 checkpoint。
诚实声明同 stage1：本阶段=系统性挖掘，结论只能出自 Stage-2 四关。
"""
from __future__ import annotations

import json
import os
import sys
from itertools import product
from multiprocessing import Pool
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))

import numpy as np
import pandas as pd

CACHE = LAB / "data" / "ohlcv_cache"
REPORTS = LAB / "reports"
OUT_CSV = REPORTS / "gate_sweep_grid.csv"
DISCOVERY_END = np.datetime64("2024-12-31")
COST = 0.0013
CONFIRM_DAYS = 2
COOLDOWN = 5

KDJ_NS = [21, 34, 55]
KDJ_THRS = [15, 20, 25, 30]
EVENTS = [f"tm{n}_{t}" for n in KDJ_NS for t in KDJ_THRS] + \
         ["trend_up", "var11", "strong_rev", "caopan_x"]
CONFIRMS = ["none", "ma20_w5", "ma20_w10", "ma20_w15", "ma20_w20", "muma_w10", "trendst_w10"]
EXITS = ["guanbian_dn", "trend_dn", "v1_tp_or_td", "water_slope",
         "ndaylow5", "ndaylow10", "ndaylow20", "hold10", "hold20", "hold30",
         "zhz_break", "giveback"]
MIN_HOLDS = [0, 10, 20]
FILTERS = ["none", "mkt_ma60", "mkt_ma20"]

_G: dict = {}


def _load_index_filters():
    path = LAB / "data" / "index_000300.csv"
    df = pd.read_csv(path, parse_dates=["date"], index_col="date").astype(float)
    out = {}
    for w in (20, 60):
        out[f"mkt_ma{w}"] = (df["close"] > df["close"].rolling(w).mean())
    return out


def worker_init():
    """每个 worker 进程加载一次：行情 + 全部信号变体 + 主日历映射。"""
    from tdx_lab.indicators import compute_xhmain, compute_xhsub, compute_xhwater, sma_tdx

    idx_filters = _load_index_filters()
    stocks = []
    all_dates = set()
    for f in sorted(CACHE.glob("*.csv")):
        df = pd.read_csv(f, parse_dates=["date"]).astype(
            {"open": float, "high": float, "low": float, "close": float, "volume": float})
        if len(df) < 120:
            continue
        c, h, l = df["close"].values, df["high"].values, df["low"].values
        n = len(c)
        sub = compute_xhsub(df)
        main = compute_xhmain(df)
        water = compute_xhwater(df)

        events = {}
        for kn in KDJ_NS:
            llv = pd.Series(l).rolling(kn).min().values
            hhv = pd.Series(h).rolling(kn).max().values
            az1 = np.where(hhv != llv, (c - llv) / (hhv - llv) * 100, 50.0)
            az3 = sma_tdx(sma_tdx(az1, 3, 1), 3, 1)
            az4 = sma_tdx(az3, 3, 1)
            cross = np.zeros(n, bool)
            cross[1:] = (az3[1:] > az4[1:]) & (az3[:-1] <= az4[:-1])
            for thr in KDJ_THRS:
                events[f"tm{kn}_{thr}"] = cross & (az3 < thr)
        caopan = main["cao_pan"]
        cpx = np.zeros(n, bool)
        cpx[1:] = caopan[1:] & ~caopan[:-1]
        events.update({"trend_up": main["trend_up"].astype(bool),
                       "var11": main["var11"].astype(bool),
                       "strong_rev": main["strong_reversal"].astype(bool),
                       "caopan_x": cpx})

        ma20 = pd.Series(c).rolling(20).mean().values
        confirms = {"ma20": c > ma20, "muma": main["mu_ma"].astype(bool),
                    "trendst": np.nan_to_num(main["cxhzb"]) >= np.nan_to_num(main["gzz"])}

        zhz = sub["zhz"]
        zb = np.zeros(n, bool)
        zb[1:] = (zhz[1:] < 0) & (zhz[:-1] >= 0)
        exits = {"guanbian_dn": ~sub["hold_line"],
                 "trend_dn": main["trend_down"].astype(bool),
                 "v1_tp_or_td": (~sub["hold_line"]) | main["trend_down"].astype(bool),
                 "water_slope": np.nan_to_num(water["water_slope_3"]) < 0,
                 "zhz_break": zb,
                 "_zeros": np.zeros(n, bool)}
        for w in (5, 10, 20):
            llvw = pd.Series(c).rolling(w).min().shift(1).values
            exits[f"ndaylow{w}"] = c < np.nan_to_num(llvw, nan=-np.inf)

        dates = df["date"].values.astype("datetime64[D]")
        all_dates.update(dates.tolist())
        mkt = {k: v.reindex(pd.DatetimeIndex(df["date"])).fillna(False).values
               for k, v in idx_filters.items()}
        stocks.append({"code": f.stem.split(".")[1], "dates": dates,
                       "o": df["open"].values, "h": h, "l": l, "c": c,
                       "events": events, "confirms": confirms, "exits": exits, "mkt": mkt})

    master = np.array(sorted(all_dates), dtype="datetime64[D]")
    for s in stocks:
        s["pos"] = np.searchsorted(master, s["dates"])
    years = np.array([d.astype("datetime64[Y]").astype(int) + 1970 for d in master])
    _G.update(stocks=stocks, master=master, years=years,
              disc_mask=master <= DISCOVERY_END)
    print(f"[worker {os.getpid()}] loaded {len(stocks)} stocks, "
          f"{len(master)} master days", flush=True)


def portfolio_from_curves(pos_list, eq_list):
    master = _G["master"]
    m = len(master)
    mat = np.full((m, len(eq_list)), np.nan)
    for j, (pos, eq) in enumerate(zip(pos_list, eq_list)):
        mat[pos, j] = eq
    # ffill + 上市前=1.0
    idx = np.where(~np.isnan(mat), np.arange(m)[:, None], 0)
    np.maximum.accumulate(idx, axis=0, out=idx)
    mat = mat[idx, np.arange(mat.shape[1])[None, :]]
    mat[np.isnan(mat)] = 1.0
    return mat.mean(axis=1)


def eval_combo(combo):
    from tdx_lab.event_engine import entry_from_event_confirm, simulate_events

    event, confirm, exit_name, min_hold, filt = combo
    pos_list, eq_list = [], []
    n_trades = wins = 0
    for s in _G["stocks"]:
        entry = s["events"][event]
        if confirm != "none":
            cname, w = confirm.rsplit("_w", 1)
            entry = entry_from_event_confirm(entry, s["confirms"][cname], int(w))
        if filt != "none":
            entry = entry & s["mkt"][filt]
        exit_arr = s["exits"]["_zeros"] if exit_name.startswith(("hold", "giveback")) \
            else s["exits"][exit_name]
        max_hold = int(exit_name[4:]) if exit_name.startswith("hold") else None
        r = simulate_events(s["o"], s["h"], s["l"], s["c"], entry, exit_arr,
                            code=s["code"], cost=COST, min_hold=min_hold,
                            max_hold=max_hold, confirm_days=CONFIRM_DAYS,
                            cooldown=COOLDOWN,
                            giveback=(0.30, 0.5) if exit_name == "giveback" else None)
        pos_list.append(s["pos"])
        eq_list.append(r["equity"])
        disc_last = np.searchsorted(s["dates"], DISCOVERY_END, side="right")
        for t in r["trades"]:
            if t["exit_idx"] < disc_last:
                n_trades += 1
                wins += t["return_pct"] > 0

    port = portfolio_from_curves(pos_list, eq_list)
    disc = port[_G["disc_mask"]]
    n = len(disc)
    cagr = disc[-1] ** (252 / n) - 1 if n else 0.0
    peak = np.maximum.accumulate(disc)
    maxdd = float((disc / peak - 1).min())
    calmar = cagr / abs(maxdd) if maxdd < 0 else (float("inf") if cagr > 0 else 0.0)
    yrs = _G["years"][_G["disc_mask"]]
    by_year = {}
    for y in np.unique(yrs):
        seg = disc[yrs == y]
        by_year[int(y)] = round(float(seg[-1] / seg[0] - 1) * 100, 1)
    return {"event": event, "confirm": confirm, "exit": exit_name,
            "min_hold": min_hold, "filter": filt, "n_trades": n_trades,
            "win_rate": round(wins / n_trades * 100, 1) if n_trades else 0.0,
            "cagr": round(float(cagr) * 100, 2), "maxdd": round(maxdd * 100, 2),
            "calmar": round(float(calmar), 3), "by_year": json.dumps(by_year)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    combos = list(product(EVENTS, CONFIRMS, EXITS, MIN_HOLDS, FILTERS))
    registry = {"events": EVENTS, "confirms": CONFIRMS, "exits": EXITS,
                "min_holds": MIN_HOLDS, "filters": FILTERS, "total": len(combos),
                "discovery_end": str(DISCOVERY_END), "cost": COST,
                "confirm_days": CONFIRM_DAYS, "cooldown": COOLDOWN,
                "note": "pre-registered wide grid v2; conclusions only from stage2 gates"}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "gate_sweep_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    done_keys = set()
    if OUT_CSV.exists():  # 断点续跑
        prev = pd.read_csv(OUT_CSV)
        done_keys = {tuple(r) for r in prev[["event", "confirm", "exit",
                                             "min_hold", "filter"]].itertuples(index=False)}
        print(f"resume: {len(done_keys)} done")
    todo = [c for c in combos if (c[0], c[1], c[2], c[3], c[4]) not in done_keys]
    print(f"total {len(combos)}, todo {len(todo)}")

    buffer = []
    with Pool(processes=4, initializer=worker_init) as pool:
        for i, row in enumerate(pool.imap_unordered(eval_combo, todo, chunksize=8), 1):
            buffer.append(row)
            if i % 200 == 0 or i == len(todo):
                df = pd.DataFrame(buffer)
                df.to_csv(OUT_CSV, mode="a", header=not OUT_CSV.exists(),
                          index=False, encoding="utf-8-sig")
                buffer = []
                print(f"  {i}/{len(todo)} checkpointed", flush=True)
    print("DONE sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
