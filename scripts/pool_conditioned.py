# -*- coding: utf-8 -*-
"""预注册第四轮：基本面池条件化——Le 的新方向（引擎B选股 × 技术执行）。

假设（跑前写死）：深超卖事件只做"当时（PIT）基本面优选池内"的股，能把
全周期账户口径从垃圾水平（随机中位 Calmar 0.13）实质抬升。

方法要点：
- 池子用引擎B PIT 因子逐日重建：yoyni（净利同比）披露日之后才可用
  （fundamentals.pit_daily_signal，杜绝前视与幸存者偏差）；引擎A景气研究
  无法历史重建，只作实盘层人工复核，不进回测。
- 池定义 3 个（预先声明，主张只落在 P25 上，其余作邻域）：
  P25=当日截面 yoyni 前25%；P50=前50%；POS=yoyni>0。
- 对照：股票身份置换 200 次（把股 i 的成员序列换给股 j，保留池大小动态，
  切断"基本面←→个股"链接）。判定线：真池的全期与留出期 信号级 Calmar
  均 > 置换分布 p95，才认可"基本面条件含真信息"。
- 经济口径：账户级 5席/20% 随机选席 300 种子的全期中位数（回答"能不能用"）。
- 披露：yoyni 因子此前在引擎B harness 以部分重叠的样本选出（轻度污染）；
  事件 tm21_15 在发现期选出。本轮是单一预注册假设+置换对照，非新海选。
"""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SX = LAB.parent / "stock-exchange"
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(LAB / "scripts"))
sys.path.insert(0, str(SX / "scripts"))

import numpy as np
import pandas as pd

import gate_sweep as GS
import slot_portfolio as SP
from harness.fundamentals import pit_daily_signal
from unified_gate_stage2 import HOLDOUT_START, clustered_t, run

FUND_CACHE = SX / "output" / "fund_cache"
N_PERMS = 200
N_SEEDS = 300
BASE_COMBO = {"event": "tm21_15", "confirm": "none", "exit": "hold30",
              "min_hold": 0, "filter": "none"}


def build_membership(master):
    """[n_stocks × n_master] PIT yoyni 矩阵 → 三个池的成员布尔矩阵。"""
    stocks = GS._G["stocks"]
    n, m = len(stocks), len(master)
    yy = np.full((n, m), np.nan)
    for si, s in enumerate(stocks):
        prefix = "sh." if s["code"].startswith(("6", "9")) else "sz."
        f = FUND_CACHE / f"{prefix}{s['code']}.csv"
        if not f.exists():
            continue
        fd = pd.read_csv(f)
        fd = fd[fd["pubDate"].astype(str).str.len() >= 8].dropna(subset=["yoyni"])
        if not len(fd):
            continue
        vals = pit_daily_signal(s["dates"].astype("datetime64[ns]"),
                                pd.to_datetime(fd["pubDate"]), fd["yoyni"].values)
        pos = np.searchsorted(master, s["dates"])
        yy[si, pos] = vals
        # 停牌日沿用前值（scatter 后 ffill）
        row = yy[si]
        idx = np.where(~np.isnan(row))[0]
        if len(idx):
            filled = np.full(m, np.nan)
            j = np.searchsorted(idx, np.arange(m), side="right") - 1
            ok = j >= 0
            filled[ok] = row[idx[j[ok]]]
            # 上市前保持 NaN：首个有效值之前不填
            filled[:idx[0]] = np.nan
            yy[si] = filled
    # 截面分位（每日对非 NaN 排名）
    rank = np.full((n, m), np.nan)
    for d in range(m):
        col = yy[:, d]
        ok = ~np.isnan(col)
        if ok.sum() < 30:
            continue
        r = col[ok].argsort().argsort() / (ok.sum() - 1)   # 0=最差 1=最好
        rank[ok, d] = r
    pools = {"P25": rank >= 0.75, "P50": rank >= 0.50, "POS": yy > 0}
    for k, mat in pools.items():
        mat[np.isnan(rank if k != "POS" else yy)] = False
    return pools


def masks_from_matrix(mat, master):
    """成员矩阵（主日历）→ 每股自身交易日的布尔掩码列表。"""
    out = []
    for si, s in enumerate(GS._G["stocks"]):
        pos = np.searchsorted(master, s["dates"])
        out.append(mat[si, pos])
    return out


def signal_level(masks, label=""):
    overrides = []
    for si, s in enumerate(GS._G["stocks"]):
        entry = s["events"]["tm21_15"] & s["entry_ok"]
        if masks is not None:
            entry = entry & masks[si]
        overrides.append(entry)
    m, hc, trades = run(BASE_COMBO, entry_overrides=overrides, collect=True)
    t_h, _ = clustered_t(trades, start=HOLDOUT_START)
    t_f, _ = clustered_t(trades)
    # 全期 Calmar：run() 只给留出期——用全期 trades 近似不行，须重算组合曲线。
    return m, t_h, t_f, trades, overrides


def full_period_calmar(overrides):
    """全期组合 Calmar（等权 399 槽，与 gate_sweep 同口径但不截留出期）。"""
    pos_list, eq_list = [], []
    for si, s in enumerate(GS._G["stocks"]):
        from unified_gate_stage2 import sim
        r = sim(s, BASE_COMBO, overrides[si])
        pos_list.append(s["pos"])
        eq_list.append(r["equity"])
    curve = GS.portfolio_from_curves(pos_list, eq_list)
    eq = curve[~np.isnan(curve)]
    if len(eq) < 100:
        return 0.0
    years = len(eq) / 244
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1
    peak = np.maximum.accumulate(eq)
    dd = float(((eq - peak) / peak).min())
    return round(float(cagr / abs(dd)) if dd < 0 else 0.0, 3)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    GS.worker_init()
    stocks = GS._G["stocks"]
    all_dates = set()
    for s in stocks:
        all_dates.update(s["dates"].tolist())
    master = np.array(sorted(all_dates), dtype="datetime64[D]")

    pools = build_membership(master)
    rows = []

    # 基线
    m0, t_h0, t_f0, tr0, ov0 = signal_level(None)
    fc0 = full_period_calmar(ov0)
    n_hold0 = sum(1 for t in tr0 if t["entry_date"] >= HOLDOUT_START)
    print(f"{'基线(无条件)':<16} 留出Calmar {m0['holdout_calmar']:>7} t {t_h0:.2f} "
          f"全期Calmar {fc0:>7} 笔数 {len(tr0)}(留出{n_hold0})")
    rows.append({"pool": "none", "hold_calmar": m0["holdout_calmar"],
                 "hold_t": round(t_h0, 2), "full_calmar": fc0,
                 "trades": len(tr0), "hold_trades": n_hold0})

    rng = np.random.default_rng(20260706)
    for name, mat in pools.items():
        masks = masks_from_matrix(mat, master)
        m, t_h, t_f, tr, ov = signal_level(masks)
        fc = full_period_calmar(ov)
        n_hold = sum(1 for t in tr if t["entry_date"] >= HOLDOUT_START)
        avg_pool = float(np.nanmean(mat.sum(axis=0)[200:]))
        print(f"{name:<16} 留出Calmar {m['holdout_calmar']:>7} t {t_h:.2f} "
              f"全期Calmar {fc:>7} 笔数 {len(tr)}(留出{n_hold}) 池均值 {avg_pool:.0f}只")
        row = {"pool": name, "hold_calmar": m["holdout_calmar"],
               "hold_t": round(t_h, 2), "full_calmar": fc,
               "trades": len(tr), "hold_trades": n_hold,
               "avg_pool_size": round(avg_pool, 0)}

        if name == "P25":   # 置换对照只跑主假设（省算力）
            null_full, null_hold = [], []
            for p in range(N_PERMS):
                perm = rng.permutation(len(stocks))
                pmasks = masks_from_matrix(mat[perm], master)
                overrides = [s["events"]["tm21_15"] & s["entry_ok"] & pmasks[si]
                             for si, s in enumerate(stocks)]
                mm, _, _ = run(BASE_COMBO, entry_overrides=overrides)
                null_hold.append(mm["holdout_calmar"])
                null_full.append(full_period_calmar(overrides))
                if (p + 1) % 50 == 0:
                    print(f"  置换 {p+1}/{N_PERMS}", flush=True)
            nh, nf = np.array(null_hold), np.array(null_full)
            row["perm_hold_p95"] = round(float(np.percentile(nh, 95)), 3)
            row["perm_full_p95"] = round(float(np.percentile(nf, 95)), 3)
            row["hold_pctile"] = round(float((nh < m["holdout_calmar"]).mean() * 100), 1)
            row["full_pctile"] = round(float((nf < fc).mean() * 100), 1)
            print(f"  置换对照: 留出分位 {row['hold_pctile']} (p95={row['perm_hold_p95']}) "
                  f"全期分位 {row['full_pctile']} (p95={row['perm_full_p95']})")

            # 账户级经济口径（300 种子全期中位）
            emasks = masks
            _, _, by_day = SP.build_event_table(entry_masks=emasks)
            SP.SEAT_CAP = 0.20
            fc_acct = []
            for seed in range(N_SEEDS):
                eq, _, _ = SP.simulate_account(master, by_day, "random", seed, slots=5)
                fc_acct.append(SP.metrics(eq, master)["calmar"])
            fa = np.array(fc_acct)
            row["acct_full_calmar_med"] = round(float(np.median(fa)), 3)
            row["acct_full_calmar_p5"] = round(float(np.percentile(fa, 5)), 3)
            row["acct_full_calmar_p95"] = round(float(np.percentile(fa, 95)), 3)
            print(f"  账户级(5席/20%)全期Calmar: 中位 {row['acct_full_calmar_med']} "
                  f"[p5 {row['acct_full_calmar_p5']}, p95 {row['acct_full_calmar_p95']}]"
                  f" vs 无条件基线全期中位 0.13")
        rows.append(row)

    pd.DataFrame(rows).to_csv(GS.REPORTS / "pool_conditioned.csv", index=False,
                              encoding="utf-8-sig")
    print("\n预注册判定：P25 须 全期与留出期信号级 Calmar 均 > 置换 p95")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
