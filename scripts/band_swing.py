# -*- coding: utf-8 -*-
"""预注册第五轮：强势股布林波段（下轨买/上轨卖）——Le 提案。

诚实声明：对同一段历史的第五轮挖掘，门槛从 p95 提至 p99。
先验披露：上轨卖=止盈退出家族（历轮全灭）；下轨买=回调入场（确认器家族全灭）。

网格（跑前写死，8 格 × 2 宇宙）：
- 强势: rs_top3(120日收益截面前1/3, PIT) | ma55up(站上MA55且MA55上行)
- 轨道: 布林20日 k∈{2.0, 1.5}；买=收盘≤下轨(次日开盘成交)；卖=收盘≥上轨
- max_hold ∈ {None, 60}；cooldown 5；confirm_days=1；成本双边0.26%
- 宇宙: U399(存续偏差修正) 主 | UAI(AI池84只, 2026年构建→历史回测幸存者偏差, 仅参考)
主格 = U399 × rs_top3 × k2.0 × mh None。
5b 附加（Le 澄清原意后加测，同判定规则）: 轨道="趋顶趋底"的因果版
  EMA(EMA(H,25),25)/EMA(EMA(L,25),25)（原式 XMA 为未来函数已禁用，此为实盘可得的
  无前视近似）× 强势 {rs_top3, ma55up} × mh {None, 60}。
对照 = 400 次同强势条件随机入场日(每股笔数配平)、同退出规则。
判定线: 主格留出期 聚类t≥2 且 Calmar>0 且 >对照 p99 且 全期 Calmar>0。
"""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SX = LAB.parent / "stock-exchange"
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(LAB / "scripts"))

import numpy as np
import pandas as pd

import gate_sweep as GS
from tdx_lab.event_engine import simulate_events
from unified_gate_stage2 import HOLDOUT_START, clustered_t

COST = 0.0013
N_CONTROLS = 400
AI_CACHE = SX / "output" / "ohlc_cache"


def entry_ok_of(c, dates):
    pct = np.abs(np.diff(c) / c[:-1])
    max40 = pd.Series(np.concatenate([[np.nan], pct])).rolling(40).max().values
    ok = ~(max40 <= 0.055)
    if dates[-1] < np.datetime64("2026-06-01"):
        ok[max(0, len(c) - 120):] = False
    return ok


def load_ai_universe():
    import csv
    codes = set()
    for row in csv.reader(open(SX / "docs" / "ai_universe.csv", encoding="utf-8")):
        if row and not row[0].startswith("#") and row[0] != "tier":
            codes.add(row[2])
    stocks = []
    for code in sorted(codes):
        bao = ("sh." if code.startswith(("6", "9")) else "sz.") + code
        f = AI_CACHE / f"{bao}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, parse_dates=["date"])
        if len(df) < 120:
            continue
        dates = df["date"].values.astype("datetime64[D]")
        c = df["close"].values.astype(float)
        stocks.append({"code": code, "dates": dates,
                       "o": df["open"].values.astype(float),
                       "h": df["high"].values.astype(float),
                       "l": df["low"].values.astype(float), "c": c,
                       "entry_ok": entry_ok_of(c, dates)})
    return stocks


def prep(stocks):
    """布林轨/MA55强势/120日收益 + 主日历与截面强势排名。"""
    all_dates = set()
    for s in stocks:
        all_dates.update(s["dates"].tolist())
    master = np.array(sorted(all_dates), dtype="datetime64[D]")
    m = len(master)
    ret120 = np.full((len(stocks), m), np.nan)
    for si, s in enumerate(stocks):
        c = s["c"]
        cs = pd.Series(c)
        m20 = cs.rolling(20).mean().values
        sd20 = cs.rolling(20).std().values
        s["bb"] = {k: (m20 - k * sd20, m20 + k * sd20) for k in (2.0, 1.5)}
        # 5b: 趋顶趋底因果版（双重EMA25 of H/L，替代未来函数XMA）
        qd_lo = pd.Series(s["l"]).ewm(span=25, adjust=False).mean() \
            .ewm(span=25, adjust=False).mean().values
        qd_hi = pd.Series(s["h"]).ewm(span=25, adjust=False).mean() \
            .ewm(span=25, adjust=False).mean().values
        s["bb"]["qd"] = (qd_lo, qd_hi)
        ma55 = cs.rolling(55).mean().values
        ma55_prev = np.concatenate([[np.nan] * 5, ma55[:-5]])
        s["ma55up"] = (c > np.nan_to_num(ma55, nan=np.inf)) & (ma55 > ma55_prev)
        r = np.full(len(c), np.nan)
        r[120:] = c[120:] / c[:-120] - 1
        s["pos_m"] = np.searchsorted(master, s["dates"])
        ret120[si, s["pos_m"]] = r
    # 截面前1/3（逐日、只对非NaN排名）
    rs = np.zeros(ret120.shape, bool)
    for d in range(m):
        col = ret120[:, d]
        ok = ~np.isnan(col)
        if ok.sum() < 15:
            continue
        thr = np.nanpercentile(col[ok], 100 * 2 / 3)
        rs[:, d] = ok & (col >= thr)
    for si, s in enumerate(stocks):
        s["rs_top3"] = rs[si, s["pos_m"]]
    return master


def portfolio_curve(pos_list, eq_list, m):
    mat = np.full((m, len(eq_list)), np.nan)
    for j, (pos, eq) in enumerate(zip(pos_list, eq_list)):
        mat[pos, j] = eq
    idx = np.where(~np.isnan(mat), np.arange(m)[:, None], 0)
    np.maximum.accumulate(idx, axis=0, out=idx)
    mat = mat[idx, np.arange(mat.shape[1])[None, :]]
    mat[np.isnan(mat)] = 1.0
    return mat.mean(axis=1)


def calmar_of(curve):
    eq = curve[~np.isnan(curve)]
    if len(eq) < 100:
        return 0.0, 0.0, 0.0
    years = len(eq) / 244
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1
    peak = np.maximum.accumulate(eq)
    dd = float(((eq - peak) / peak).min())
    cal = float(cagr / abs(dd)) if dd < 0 else 0.0
    return round(cal, 3), round(cagr * 100, 2), round(dd * 100, 2)


def run_cells(stocks, master, strength_key, k, max_hold, entries_override=None):
    pos_list, eq_list, trades = [], [], []
    m = len(master)
    for si, s in enumerate(stocks):
        lower, upper = s["bb"][k]
        if entries_override is not None:
            entry = entries_override[si]
        else:
            entry = (s["c"] <= np.nan_to_num(lower, nan=-np.inf)) \
                & s[strength_key] & s["entry_ok"]
        exit_arr = s["c"] >= np.nan_to_num(upper, nan=np.inf)
        r = simulate_events(s["o"], s["h"], s["l"], s["c"], entry, exit_arr,
                            code=s["code"], cost=COST, min_hold=0,
                            max_hold=max_hold, confirm_days=1, cooldown=5)
        pos_list.append(s["pos_m"])
        eq_list.append(r["equity"])
        for t in r["trades"]:
            trades.append({**t, "entry_date": s["dates"][t["entry_idx"]],
                           "stock": si})
    curve = portfolio_curve(pos_list, eq_list, m)
    h0 = int(np.searchsorted(master, HOLDOUT_START))
    full = calmar_of(curve)
    hold = calmar_of(curve[h0:])
    t_h, _ = clustered_t(trades, start=HOLDOUT_START)
    rets = [t["return_pct"] for t in trades]
    hdays = [t["hold_days"] for t in trades]
    stats = {"n": len(trades), "avg_ret": round(float(np.mean(rets)), 2) if rets else 0,
             "win": round(float(np.mean([x > 0 for x in rets])) * 100, 1) if rets else 0,
             "avg_hold": round(float(np.mean(hdays)), 1) if hdays else 0}
    return full, hold, round(t_h, 2), stats, trades


def matched_controls(stocks, master, strength_key, k, max_hold, real_trades, rng):
    """同强势条件随机入场日、笔数配平、同退出规则。返回留出/全期 Calmar 分布。"""
    counts = np.zeros(len(stocks), int)
    for t in real_trades:
        counts[t["stock"]] += 1
    elig = []
    for s in stocks:
        ok = s[strength_key] & s["entry_ok"]
        idx = np.where(ok)[0]
        elig.append(idx[idx >= 120])
    null_h, null_f = [], []
    for ci in range(N_CONTROLS):
        overrides = []
        for si, s in enumerate(stocks):
            arr = np.zeros(len(s["c"]), bool)
            kk = counts[si]
            if kk and len(elig[si]):
                arr[rng.choice(elig[si], size=min(kk, len(elig[si])),
                               replace=False)] = True
            overrides.append(arr)
        full, hold, _, _, _ = run_cells(stocks, master, strength_key, k, max_hold,
                                        entries_override=overrides)
        null_f.append(full[0])
        null_h.append(hold[0])
        if (ci + 1) % 100 == 0:
            print(f"  对照 {ci+1}/{N_CONTROLS}", flush=True)
    return np.array(null_h), np.array(null_f)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    GS.worker_init()
    u399 = GS._G["stocks"]
    uai = load_ai_universe()
    rows = []
    rng = np.random.default_rng(20260707)

    for uname, stocks in (("U399", u399), ("UAI", uai)):
        master = prep(stocks)
        print(f"\n== {uname}: {len(stocks)} 只 ==")
        print(f"{'格':<28}{'留出Calmar':>10}{'留出t':>7}{'全期Calmar':>10}"
              f"{'笔数':>6}{'均收':>7}{'胜率':>6}{'均持':>6}")
        for strength in ("rs_top3", "ma55up"):
            for k in (2.0, 1.5, "qd"):
                for mh in (None, 60):
                    full, hold, t_h, st, trades = run_cells(stocks, master,
                                                            strength, k, mh)
                    label = f"{strength}|k{k}|mh{mh or '-'}"
                    print(f"{label:<28}{hold[0]:>10}{t_h:>7}{full[0]:>10}"
                          f"{st['n']:>6}{st['avg_ret']:>6}%{st['win']:>5}%"
                          f"{st['avg_hold']:>6}")
                    row = {"universe": uname, "cell": label,
                           "hold_calmar": hold[0], "hold_cagr": hold[1],
                           "hold_t": t_h, "full_calmar": full[0],
                           "full_cagr": full[1], "full_maxdd": full[2], **st}
                    if uname == "U399" and strength == "rs_top3" and k == 2.0 \
                            and mh is None:
                        print("  主格 → 400 配平对照…", flush=True)
                        nh, nf = matched_controls(stocks, master, strength, k, mh,
                                                  trades, rng)
                        row["ctrl_hold_p99"] = round(float(np.percentile(nh, 99)), 3)
                        row["ctrl_full_p99"] = round(float(np.percentile(nf, 99)), 3)
                        row["hold_pctile"] = round(float((nh < hold[0]).mean()) * 100, 1)
                        row["full_pctile"] = round(float((nf < full[0]).mean()) * 100, 1)
                        print(f"  对照: 留出分位 {row['hold_pctile']} "
                              f"(p99={row['ctrl_hold_p99']}) 全期分位 {row['full_pctile']} "
                              f"(p99={row['ctrl_full_p99']})")
                    rows.append(row)

    pd.DataFrame(rows).to_csv(GS.REPORTS / "band_swing.csv", index=False,
                              encoding="utf-8-sig")
    print("\n预注册判定：主格须 留出t≥2 且 留出Calmar>0 且 >对照p99 且 全期Calmar>0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
