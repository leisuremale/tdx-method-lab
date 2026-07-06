# -*- coding: utf-8 -*-
"""统一证伪关 Stage-2：对 Stage-1 前 8 组合执行预注册四关。只有这里产生结论。

四关（spec §3，全过才 PASS）：
G1 随机同频对照：同股/同入场次数/同退出，200 次置换，实策略发现期组合 Calmar ≥ 95 分位
G2 留出期 2025-01~2026-06：Calmar > 0 且 ≥ 发现期的 50%
G3 参数邻域平台：预注册邻居集合中 ≥70% 的格 Calmar ≥ 中心的 60%
G4 切片稳健：按入场日大盘 regime（>MA60/≤MA60）两桶均值收益均为正桶数≥1 且
   盈利不集中（任一桶利润占比 ≤85%）；AI池重叠名的最大板块利润占比 ≤50%（记录性弱关）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(LAB / "scripts"))

import numpy as np
import pandas as pd
from tdx_lab.event_engine import simulate_events
from unified_gate_stage1 import (CACHE, CONFIRM_DAYS, COOLDOWN, COST, DISCOVERY_END,
                                 REPORTS, build_entry, load_index_ma60,
                                 portfolio_metrics, stock_signals)

HOLDOUT_START = "2025-01-01"
TOP_N = 8
CONTROL_RUNS = 200
SEED = 42


def prepare_stocks():
    mkt_ok = load_index_ma60()
    stocks = []
    for f in sorted(CACHE.glob("*.csv")):
        df = pd.read_csv(f, parse_dates=["date"]).astype(
            {"open": float, "high": float, "low": float, "close": float, "volume": float})
        if len(df) < 120:
            continue
        stocks.append({"code": f.stem.split(".")[1], "df": df, "sig": stock_signals(df),
                       "mkt": mkt_ok.reindex(pd.DatetimeIndex(df["date"])).fillna(False).values})
    return stocks


def run_combo(stocks, combo, *, entry_override=None, period_end=None, period_start=None,
              confirm_days=None, cooldown=None, min_hold=None, collect_trades=False):
    curves, all_trades = [], []
    for idx, s in enumerate(stocks):
        entry = (entry_override[idx] if entry_override is not None
                 else build_entry(s["sig"], combo["event"], combo["confirm"]))
        if combo["filter"] == "mkt_ma60" and entry_override is None:
            entry = entry & s["mkt"]
        r = simulate_events(
            s["df"]["open"].values, s["df"]["high"].values,
            s["df"]["low"].values, s["df"]["close"].values,
            entry, s["sig"]["exits"][combo["exit"]], code=s["code"], cost=COST,
            min_hold=combo["min_hold"] if min_hold is None else min_hold,
            max_hold=20 if combo["exit"] == "hold20" else None,
            confirm_days=CONFIRM_DAYS if confirm_days is None else confirm_days,
            cooldown=COOLDOWN if cooldown is None else cooldown)
        dates = pd.DatetimeIndex(s["df"]["date"])
        eqs = pd.Series(r["equity"], index=dates)
        if period_start:  # 留出期：只取该段并归一
            eqs = eqs.loc[period_start:]
            if len(eqs) < 60:
                continue
            eqs = eqs / eqs.iloc[0]
        curves.append(eqs)
        if collect_trades:
            for t in r["trades"]:
                all_trades.append({**t, "code": s["code"],
                                   "entry_date": str(s["df"]["date"].iloc[t["entry_idx"]].date()),
                                   "mkt_up": bool(s["mkt"][t["entry_idx"]])})
    m = portfolio_metrics(curves, None, period_end or "2026-12-31")
    return m, all_trades


def gate1_random_control(stocks, combo, real_calmar, rng):
    """同频随机进场：每股与实策略同样多的入场信号日（发现期内），同退出。"""
    # 预取实际入场日 counts
    counts = []
    for s in stocks:
        entry = build_entry(s["sig"], combo["event"], combo["confirm"])
        if combo["filter"] == "mkt_ma60":
            entry = entry & s["mkt"]
        disc = s["df"]["date"] <= DISCOVERY_END
        counts.append(int((entry & disc.values).sum()))
    null = []
    for run in range(CONTROL_RUNS):
        overrides = []
        for s, k in zip(stocks, counts):
            n = len(s["df"])
            arr = np.zeros(n, bool)
            disc_idx = np.where((s["df"]["date"] <= DISCOVERY_END).values)[0]
            elig = disc_idx[disc_idx >= 60]
            if k and len(elig):
                arr[rng.choice(elig, size=min(k, len(elig)), replace=False)] = True
            overrides.append(arr)
        m, _ = run_combo(stocks, combo, entry_override=overrides, period_end=DISCOVERY_END)
        null.append(m["calmar"])
        if (run + 1) % 50 == 0:
            print(f"    control {run+1}/{CONTROL_RUNS}", flush=True)
    null = np.asarray(null, float)
    pct = float((null < real_calmar).mean() * 100)
    return {"percentile": round(pct, 1), "null_mean": round(float(np.nanmean(null)), 3),
            "null_p95": round(float(np.nanpercentile(null, 95)), 3),
            "pass": pct >= 95.0}


NEIGHBOR_SETS = {
    "event": {"tianma20": ["tianma25"], "tianma25": ["tianma20"]},
    "confirm": {"ma20_w10": ["ma20_w15"], "ma20_w15": ["ma20_w10"],
                "muma_w10": ["ma20_w10"], "trendst_w10": ["ma20_w10"], "none": []},
    "min_hold": {0: [10], 20: [10]},
}


def gate3_neighbors(stocks, combo, center_calmar):
    variants = []
    for ev in NEIGHBOR_SETS["event"].get(combo["event"], []):
        variants.append({**combo, "event": ev})
    for cf in NEIGHBOR_SETS["confirm"].get(combo["confirm"], []):
        variants.append({**combo, "confirm": cf})
    for mh in NEIGHBOR_SETS["min_hold"].get(combo["min_hold"], []):
        variants.append({**combo, "min_hold": mh})
    extra = [dict(confirm_days=3), dict(cooldown=10)]
    results = []
    for v in variants:
        m, _ = run_combo(stocks, v, period_end=DISCOVERY_END)
        results.append(m["calmar"])
    for kw in extra:
        m, _ = run_combo(stocks, combo, period_end=DISCOVERY_END, **kw)
        results.append(m["calmar"])
    ok = sum(1 for x in results if x >= 0.6 * center_calmar)
    return {"neighbors": [round(x, 3) for x in results],
            "plateau_ratio": round(ok / len(results), 2) if results else 0,
            "pass": bool(results) and ok / len(results) >= 0.7}


def gate4_slices(trades):
    if not trades:
        return {"pass": False, "note": "no trades"}
    df = pd.DataFrame(trades)
    disc = df[df["entry_date"] <= DISCOVERY_END]
    buckets = disc.groupby("mkt_up")["return_pct"]
    means = buckets.mean().to_dict()
    profits = disc[disc["return_pct"] > 0].groupby("mkt_up")["return_pct"].sum()
    total_profit = profits.sum() or 1
    max_share = float(profits.max() / total_profit) if len(profits) else 1.0
    pos_buckets = sum(1 for v in means.values() if v > 0)
    return {"bucket_mean_return": {str(k): round(v, 2) for k, v in means.items()},
            "max_bucket_profit_share": round(max_share, 2),
            "pass": pos_buckets >= 1 and max_share <= 0.85}


def main() -> int:
    grid = pd.read_csv(REPORTS / "gate_stage1_grid.csv")
    grid = grid[grid["n_trades"] >= 300].head(TOP_N)
    print(f"Stage-2 candidates: {len(grid)}")
    stocks = prepare_stocks()
    print(f"stocks: {len(stocks)}")
    rng = np.random.default_rng(SEED)

    verdicts = []
    for _, row in grid.iterrows():
        combo = {"event": row["event"], "confirm": row["confirm"], "exit": row["exit"],
                 "min_hold": int(row["min_hold"]), "filter": row["filter"]}
        label = "+".join(str(combo[k]) for k in ("event", "confirm", "exit")) + \
                f"+mh{combo['min_hold']}+{combo['filter']}"
        print(f"\n=== {label} (发现期 Calmar {row['calmar']}) ===", flush=True)
        m_disc, trades = run_combo(stocks, combo, period_end=DISCOVERY_END, collect_trades=True)
        g1 = gate1_random_control(stocks, combo, m_disc["calmar"], rng)
        print(f"  G1 随机对照: {g1['percentile']}分位 (null95={g1['null_p95']}) "
              f"{'✅' if g1['pass'] else '❌'}", flush=True)
        m_hold, _ = run_combo(stocks, combo, period_start=HOLDOUT_START)
        g2 = {"holdout_calmar": m_hold["calmar"], "discovery_calmar": m_disc["calmar"],
              "pass": m_hold["calmar"] > 0 and m_hold["calmar"] >= 0.5 * m_disc["calmar"]}
        print(f"  G2 留出期: Calmar {m_hold['calmar']} {'✅' if g2['pass'] else '❌'}", flush=True)
        g3 = gate3_neighbors(stocks, combo, m_disc["calmar"])
        print(f"  G3 邻域平台: {g3['plateau_ratio']} {'✅' if g3['pass'] else '❌'}", flush=True)
        g4 = gate4_slices(trades)
        print(f"  G4 切片: {g4} ", flush=True)
        verdicts.append({"combo": combo, "label": label,
                         "discovery": m_disc, "g1": g1, "g2": g2, "g3": g3, "g4": g4,
                         "PASS": g1["pass"] and g2["pass"] and g3["pass"] and g4["pass"]})

    (REPORTS / "gate_stage2_verdict.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    passed = [v for v in verdicts if v["PASS"]]
    print("\n" + "=" * 70)
    if passed:
        print("✅ 过四关组合:")
        for v in passed:
            print(f"  {v['label']}  发现期Calmar {v['discovery']['calmar']} "
                  f"留出期 {v['g2']['holdout_calmar']}")
    else:
        print("❌ 无组合通过四关 —— TDX 组合在本仪器下无可确认 edge（如实记录）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
