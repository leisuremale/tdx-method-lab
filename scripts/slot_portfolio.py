# -*- coding: utf-8 -*-
"""P1 资金约束组合回测：V-final 信号在 真实账户口径（20万/3席/30%单席上限）下的表现。

回测口径(399槽等权、均值50只在场) → 账户口径 的映射测试。
席位选择规则本身先过随机对照（防止又一轮挖掘）：
- random：同日候选随机挑，500 种子 → 账户级指标分布 = 无信息基线
- deep_oversold(信号日az3最低) / turnover(20日成交额最大)：确定性单值
预注册判定（跑前写死）：排序规则的留出期 Calmar ≥ 随机分布 95 分位才认可其
含信息；否则系统预期按随机中位数汇报，运营层用字典序（无信息但可复现）。
披露的近似：账户跳过某信号不回改该股后续信号序列（忽略账户视角冷却漂移）；
停牌日持仓按最后收盘价计值。
"""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(LAB / "scripts"))

import numpy as np
import pandas as pd

import gate_sweep as GS
from tdx_lab.event_engine import simulate_events
from tdx_lab.indicators import sma_tdx

START_CAPITAL = 200_000.0
MAX_SLOTS = 3
SEAT_CAP = 0.30          # 单席 ≤ 30% 总权益
COST_SIDE = 0.0013
RANDOM_SEEDS = 500
HOLDOUT = np.datetime64("2025-01-01")


def build_event_table():
    """每股跑一遍 V-final 引擎，汇成全局事件表（含排序特征）。"""
    stocks = GS._G["stocks"]
    all_dates = set()
    for s in stocks:
        all_dates.update(s["dates"].tolist())
    master = np.array(sorted(all_dates), dtype="datetime64[D]")

    events = []
    for si, s in enumerate(stocks):
        entry = s["events"]["tm21_15"] & s["entry_ok"]
        r = simulate_events(s["o"], s["h"], s["l"], s["c"], entry,
                            s["exits"]["_zeros"], code=s["code"], cost=COST_SIDE,
                            min_hold=0, max_hold=30, confirm_days=GS.CONFIRM_DAYS,
                            cooldown=GS.COOLDOWN)
        if not r["trades"]:
            continue
        c = s["c"]
        # 排序特征：信号日 az3（越低越超卖）、20日均成交额
        kn, n = 21, len(c)
        llv = pd.Series(s["l"]).rolling(kn).min().values
        hhv = pd.Series(s["h"]).rolling(kn).max().values
        az1 = np.where(hhv != llv, (c - llv) / (hhv - llv) * 100, 50.0)
        az3 = sma_tdx(sma_tdx(az1, 3, 1), 3, 1)
        prefix = "sh." if s["code"].startswith(("6", "9")) else "sz."
        vol = pd.read_csv(GS.CACHE / f"{prefix}{s['code']}.csv")["volume"] \
            .values.astype(float)[-n:]
        turn20 = pd.Series(vol * c).rolling(20).mean().values
        pos = np.searchsorted(master, s["dates"])   # 股票日 → 主日历位
        for t in trades_sorted(r["trades"]):
            ei, xi = t["entry_idx"], t["exit_idx"]
            sig = max(0, ei - 1)
            events.append({
                "stock": si, "code": s["code"],
                "m_entry": int(pos[ei]), "m_exit": int(pos[xi]),
                "entry_price": t["entry_price"], "exit_price": t["exit_price"],
                "az3": float(az3[sig]) if np.isfinite(az3[sig]) else 50.0,
                "turn": float(turn20[sig]) if np.isfinite(turn20[sig]) else 0.0,
                "pos_map": pos, "c": c,
            })
    by_day: dict[int, list] = {}
    for ev in events:
        by_day.setdefault(ev["m_entry"], []).append(ev)
    return master, events, by_day


def trades_sorted(trades):
    return sorted(trades, key=lambda t: t["entry_idx"])


def mark_price(ev, m_day):
    """主日历某天该股的最后已知收盘价（停牌沿用前值）。"""
    j = np.searchsorted(ev["pos_map"], m_day, side="right") - 1
    return ev["c"][max(j, 0)]


def simulate_account(master, by_day, rule, seed=0, slots=MAX_SLOTS):
    rng = np.random.default_rng(seed)
    cash, held = START_CAPITAL, {}    # held: stock_idx -> position dict
    equity = np.empty(len(master))
    trades_taken = 0
    occupancy = 0
    for d in range(len(master)):
        # 1) 退出（开盘卖出，跌停顺延已折进 engine 的 exit 事实）
        for si in [k for k, p in held.items() if p["m_exit"] == d]:
            p = held.pop(si)
            cash += p["shares"] * p["ev"]["exit_price"] * (1 - COST_SIDE)
        # 2) 入场候选
        cands = [ev for ev in by_day.get(d, [])
                 if ev["stock"] not in held]
        free = slots - len(held)
        if cands and free > 0:
            if rule == "random":
                rng.shuffle(cands)
            elif rule == "deep_oversold":
                cands.sort(key=lambda e: e["az3"])
            elif rule == "turnover":
                cands.sort(key=lambda e: -e["turn"])
            elif rule == "lexico":
                cands.sort(key=lambda e: e["code"])
            total_eq = cash + sum(p["shares"] * mark_price(p["ev"], d)
                                  for p in held.values())
            for ev in cands[:free]:
                budget = min(SEAT_CAP * total_eq, cash)
                shares = int(budget / (ev["entry_price"] * (1 + COST_SIDE) * 100)) * 100
                if shares <= 0:
                    continue
                cost = shares * ev["entry_price"] * (1 + COST_SIDE)
                cash -= cost
                held[ev["stock"]] = {"shares": shares, "m_exit": ev["m_exit"], "ev": ev}
                trades_taken += 1
        # 3) 每日市值
        equity[d] = cash + sum(p["shares"] * mark_price(p["ev"], d)
                               for p in held.values())
        occupancy += len(held)
    return equity, trades_taken, occupancy / len(master)


def metrics(equity, master, start=None):
    if start is not None:
        i0 = int(np.searchsorted(master, start))
        eq = equity[i0:]
    else:
        eq = equity
    if len(eq) < 40 or eq[0] <= 0:
        return {"cagr": 0.0, "maxdd": 0.0, "calmar": 0.0}
    years = len(eq) / 244
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1
    peak = np.maximum.accumulate(eq)
    maxdd = float(((eq - peak) / peak).min())
    calmar = cagr / abs(maxdd) if maxdd < 0 else (np.inf if cagr > 0 else 0.0)
    return {"cagr": round(cagr * 100, 2), "maxdd": round(maxdd * 100, 2),
            "calmar": round(float(calmar), 3)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    GS.worker_init()
    master, events, by_day = build_event_table()
    print(f"事件表: {len(events)} 笔可执行信号事件, 主日历 {len(master)} 天")

    rows = []
    # 随机基线分布
    rand_hold_calmar, rand_full = [], []
    for seed in range(RANDOM_SEEDS):
        eq, n_tr, occ = simulate_account(master, by_day, "random", seed)
        mh = metrics(eq, master, HOLDOUT)
        mf = metrics(eq, master)
        rand_hold_calmar.append(mh["calmar"])
        rand_full.append((mf["calmar"], mf["cagr"], mf["maxdd"],
                          mh["cagr"], mh["maxdd"], n_tr, occ))
    rc = np.array(rand_hold_calmar)
    rf = np.array([x[0] for x in rand_full])
    print(f"\n随机规则 500 种子（无信息基线）:")
    print(f"  留出Calmar 中位 {np.median(rc):.3f}  p5 {np.percentile(rc,5):.3f}  "
          f"p95 {np.percentile(rc,95):.3f}")

    for rule in ("deep_oversold", "turnover", "lexico"):
        eq, n_tr, occ = simulate_account(master, by_day, rule)
        mh, mf = metrics(eq, master, HOLDOUT), metrics(eq, master)
        pct = float((rc < mh["calmar"]).mean() * 100)
        rows.append({"rule": rule, **{f"hold_{k}": v for k, v in mh.items()},
                     **{f"full_{k}": v for k, v in mf.items()},
                     "trades": n_tr, "occupancy": round(occ, 2),
                     "pctile_vs_random": round(pct, 1)})
        print(f"  {rule:<14} 留出Calmar {mh['calmar']:>7}  CAGR {mh['cagr']:>6}%  "
              f"MaxDD {mh['maxdd']:>7}%  全期Calmar {mf['calmar']:>7}  "
              f"成交{n_tr}  占席率{occ:.2f}  随机分位{pct:.0f}")

    # 随机分布汇总也落盘
    med = int(np.argsort(rc)[len(rc) // 2])
    eq, n_tr, occ = simulate_account(master, by_day, "random", med)
    mh, mf = metrics(eq, master, HOLDOUT), metrics(eq, master)
    rows.append({"rule": f"random_median(seed{med})",
                 **{f"hold_{k}": v for k, v in mh.items()},
                 **{f"full_{k}": v for k, v in mf.items()},
                 "trades": n_tr, "occupancy": round(occ, 2),
                 "pctile_vs_random": 50.0})
    dist = {"rand_hold_calmar_med": float(np.median(rc)),
            "rand_hold_calmar_p5": float(np.percentile(rc, 5)),
            "rand_hold_calmar_p95": float(np.percentile(rc, 95)),
            "rand_full_calmar_med": float(np.median(rf)),
            "rand_hold_cagr_med": float(np.median([x[3] for x in rand_full])),
            "rand_hold_maxdd_med": float(np.median([x[4] for x in rand_full])),
            "rand_trades_med": float(np.median([x[5] for x in rand_full])),
            "rand_occupancy_med": float(np.median([x[6] for x in rand_full]))}
    pd.DataFrame(rows).to_csv(GS.REPORTS / "slot_portfolio.csv", index=False,
                              encoding="utf-8-sig")
    import json
    (GS.REPORTS / "slot_portfolio_random_dist.json").write_text(
        json.dumps(dist, indent=2), encoding="utf-8")
    print(f"\n随机基线: {dist}")
    print("预注册判定：排序规则须 ≥ 随机 p95 才认可含信息；否则运营用字典序、"
          "预期按随机中位数汇报")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
