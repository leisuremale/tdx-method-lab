# -*- coding: utf-8 -*-
"""统一证伪关 Stage-2 v2（按 2026-07-06 对抗审计加固）：一切检验在留出期进行。

审计结论采纳：发现期检验被选择污染（C3）→ 置换对照/邻域/绝对判据全部搬到
留出期 2025-01~2026-07；随机对照与实策略同条件（过滤日抽样+按实际成交笔数
配平，C2/m4）；留出期不剔除短样本股（M2）；G4 用净利润与年度集中度（M3）。

预注册四关（全过=PASS；任何一关失败即 FAIL，不允许事后调整标准）：
G1 留出期置换对照：400 次随机同频（同股/同成交笔数/同过滤条件/同退出），
   实策略留出期组合 Calmar ≥ null 的 99.4 分位（8 候选 Bonferroni）
G2 留出期绝对：按周聚类 t ≥ 2.0 且 组合 Calmar > 0
G3 邻域平台（留出期）：预注册邻居 ≥70% 的格 Calmar ≥ 中心的 60%
G4 集中度：发现期任一年净收益贡献 ≤85%；按入场日大盘桶净利润占比 ≤85%
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(LAB / "scripts"))

import numpy as np
import pandas as pd

import gate_sweep as GS
from tdx_lab.event_engine import entry_from_event_confirm, simulate_events

HOLDOUT_START = np.datetime64("2025-01-01")
TOP_N = 8
MIN_TRADES = 800
CONTROL_RUNS = 400
BONFERRONI_PCT = 99.4
SEED = 42
REPORTS = GS.REPORTS


def build_entry(s, combo):
    entry = s["events"][combo["event"]]
    if combo["confirm"] != "none":
        cname, w = combo["confirm"].rsplit("_w", 1)
        entry = entry_from_event_confirm(entry, s["confirms"][cname], int(w))
    if combo["filter"] != "none":
        entry = entry & s["mkt"][combo["filter"]]
    return entry & s["entry_ok"]


def sim(s, combo, entry):
    exit_arr = s["exits"]["_zeros"] if combo["exit"].startswith(("hold", "giveback")) \
        else s["exits"][combo["exit"]]
    max_hold = int(combo["exit"][4:]) if combo["exit"].startswith("hold") else None
    return simulate_events(s["o"], s["h"], s["l"], s["c"], entry, exit_arr,
                           code=s["code"], cost=GS.COST, min_hold=combo["min_hold"],
                           max_hold=max_hold, confirm_days=combo.get("confirm_days", GS.CONFIRM_DAYS),
                           cooldown=combo.get("cooldown", GS.COOLDOWN),
                           giveback=(0.30, 0.5) if combo["exit"] == "giveback" else None)


def run(combo, entry_overrides=None, collect=False):
    """全期运行 → (留出期组合指标, 留出期每股成交笔数, 交易明细)。"""
    pos_list, eq_list, hold_counts, trades = [], [], [], []
    for idx, s in enumerate(GS._G["stocks"]):
        entry = entry_overrides[idx] if entry_overrides is not None else build_entry(s, combo)
        r = sim(s, combo, entry)
        pos_list.append(s["pos"])
        eq_list.append(r["equity"])
        h0 = np.searchsorted(s["dates"], HOLDOUT_START)
        hold_counts.append(sum(1 for t in r["trades"] if t["entry_idx"] >= h0))
        if collect:
            for t in r["trades"]:
                trades.append({**t, "code": s["code"],
                               "entry_date": s["dates"][t["entry_idx"]],
                               "mkt_up": bool(s["mkt"]["mkt_ma60"][t["entry_idx"]])})
    port = GS.portfolio_from_curves(pos_list, eq_list)
    master = GS._G["master"]
    hmask = master >= HOLDOUT_START
    hp = port[hmask]
    hp = hp / hp[0]
    n = len(hp)
    cagr = hp[-1] ** (252 / n) - 1
    peak = np.maximum.accumulate(hp)
    maxdd = float((hp / peak - 1).min())
    calmar = cagr / abs(maxdd) if maxdd < 0 else (float("inf") if cagr > 0 else 0.0)
    return {"holdout_calmar": round(float(calmar), 3),
            "holdout_cagr": round(float(cagr) * 100, 2),
            "holdout_maxdd": round(maxdd * 100, 2)}, hold_counts, trades


def clustered_t(trades, start=None, end=None):
    weeks: dict = {}
    for t in trades:
        d = t["entry_date"]
        if (start is not None and d < start) or (end is not None and d > end):
            continue
        weeks.setdefault(str(d.astype("datetime64[W]")), []).append(t["return_pct"])
    means = np.array([np.mean(v) for v in weeks.values()])
    k = len(means)
    if k < 8 or means.std(ddof=1) == 0:
        return 0.0, k
    return float(means.mean() / (means.std(ddof=1) / np.sqrt(k))), k


def gate1(combo, real_calmar, hold_counts, rng):
    """留出期置换：同过滤条件日抽样 + 按实际成交笔数配平（审计C2/m4）。"""
    stocks = GS._G["stocks"]
    elig_cache = []
    for s in stocks:
        h0 = np.searchsorted(s["dates"], HOLDOUT_START)
        ok = s["entry_ok"].copy()
        if combo["filter"] != "none":
            ok = ok & s["mkt"][combo["filter"]]
        idx = np.where(ok)[0]
        elig_cache.append(idx[(idx >= max(60, h0))])
    null = np.empty(CONTROL_RUNS)
    for run_i in range(CONTROL_RUNS):
        overrides = []
        for s, k, elig in zip(stocks, hold_counts, elig_cache):
            arr = np.zeros(len(s["c"]), bool)
            if k and len(elig):
                arr[rng.choice(elig, size=min(k, len(elig)), replace=False)] = True
            overrides.append(arr)
        m, _, _ = run(combo, entry_overrides=overrides)
        null[run_i] = m["holdout_calmar"]
        if (run_i + 1) % 100 == 0:
            print(f"    null {run_i+1}/{CONTROL_RUNS}", flush=True)
    pct = float((null < real_calmar).mean() * 100)
    return {"percentile": round(pct, 1),
            "null_p95": round(float(np.nanpercentile(null, 95)), 3),
            "null_p994": round(float(np.nanpercentile(null, BONFERRONI_PCT)), 3),
            "pass": pct >= BONFERRONI_PCT}


def gate3(combo, center):
    neighbors = []
    ev = combo["event"]
    if ev.startswith("tm"):
        n_, thr = ev[2:].split("_")
        n_, thr = int(n_), int(thr)
        for nn in [x for x in GS.KDJ_NS if x != n_][:1]:
            neighbors.append({**combo, "event": f"tm{nn}_{thr}"})
        for tt in [t for t in GS.KDJ_THRS if abs(t - thr) == 5]:
            neighbors.append({**combo, "event": f"tm{n_}_{tt}"})
    if combo["confirm"].startswith("ma20_w"):
        w = int(combo["confirm"].rsplit("w", 1)[1])
        for ww in (w - 5, w + 5):
            if f"ma20_w{ww}" in GS.CONFIRMS:
                neighbors.append({**combo, "confirm": f"ma20_w{ww}"})
    for mh in {0: [10], 10: [0, 20], 20: [10]}.get(combo["min_hold"], []):
        neighbors.append({**combo, "min_hold": mh})
    neighbors.append({**combo, "confirm_days": 3})
    neighbors.append({**combo, "cooldown": 10})
    vals = []
    for nb in neighbors:
        m, _, _ = run(nb)
        vals.append(m["holdout_calmar"])
    ok = sum(1 for v in vals if v >= 0.6 * center)
    return {"neighbors": [round(v, 3) for v in vals],
            "plateau": round(ok / len(vals), 2) if vals else 0.0,
            "pass": bool(vals) and center > 0 and ok / len(vals) >= 0.7}


def gate4(trades):
    disc = [t for t in trades if t["entry_date"] < HOLDOUT_START]
    if not disc:
        return {"pass": False, "note": "no discovery trades"}
    df = pd.DataFrame([{"year": t["entry_date"].astype("datetime64[Y]").astype(int) + 1970,
                        "ret": t["return_pct"], "mkt_up": t["mkt_up"]} for t in disc])
    year_net = df.groupby("year")["ret"].sum()
    total = year_net.sum()
    year_share = float((year_net / total).max()) if total > 0 else 1.0
    bucket_net = df.groupby("mkt_up")["ret"].sum()
    btotal = bucket_net.sum()
    bucket_share = float((bucket_net / btotal).max()) if btotal > 0 and len(bucket_net) > 1 else 1.0
    single_bucket = len(bucket_net) <= 1  # 带市场过滤的组合天然单桶
    return {"year_net": {int(k): round(v, 1) for k, v in year_net.items()},
            "max_year_share": round(year_share, 2),
            "max_bucket_share": None if single_bucket else round(bucket_share, 2),
            "pass": total > 0 and year_share <= 0.85 and (single_bucket or bucket_share <= 0.85)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    grid = pd.read_csv(REPORTS / "gate_sweep_grid.csv")
    cand = grid[grid["n_trades"] >= MIN_TRADES].sort_values("t_stat", ascending=False).head(TOP_N)
    print(f"Stage-2 v2 candidates (n_trades>={MIN_TRADES}, by clustered-t): {len(cand)}")
    GS.worker_init()
    rng = np.random.default_rng(SEED)

    verdicts = []
    for _, row in cand.iterrows():
        combo = {"event": row["event"], "confirm": row["confirm"], "exit": row["exit"],
                 "min_hold": int(row["min_hold"]), "filter": row["filter"]}
        label = f"{combo['event']}+{combo['confirm']}+{combo['exit']}+mh{combo['min_hold']}+{combo['filter']}"
        print(f"\n=== {label} (发现期 t={row['t_stat']}, Calmar={row['calmar']}) ===", flush=True)
        real, hold_counts, trades = run(combo, collect=True)
        t_hold, k_hold = clustered_t(trades, start=HOLDOUT_START)
        print(f"  留出期: Calmar {real['holdout_calmar']} CAGR {real['holdout_cagr']}% "
              f"t={t_hold:.2f} (周簇{k_hold}, 成交{sum(hold_counts)})", flush=True)
        g1 = gate1(combo, real["holdout_calmar"], hold_counts, rng)
        print(f"  G1 留出期置换: {g1['percentile']}分位 (需≥{BONFERRONI_PCT}) "
              f"{'✅' if g1['pass'] else '❌'}", flush=True)
        g2 = {"t": round(t_hold, 2), "calmar": real["holdout_calmar"],
              "pass": t_hold >= 2.0 and real["holdout_calmar"] > 0}
        print(f"  G2 留出期绝对: {'✅' if g2['pass'] else '❌'}", flush=True)
        g3 = gate3(combo, real["holdout_calmar"])
        print(f"  G3 邻域(留出期): plateau {g3['plateau']} {'✅' if g3['pass'] else '❌'}", flush=True)
        g4 = gate4(trades)
        print(f"  G4 集中度: {g4.get('max_year_share')}/{g4.get('max_bucket_share')} "
              f"{'✅' if g4['pass'] else '❌'}", flush=True)
        verdicts.append({"combo": combo, "label": label, "holdout": real,
                         "holdout_t": round(t_hold, 2), "g1": g1, "g2": g2,
                         "g3": g3, "g4": g4,
                         "PASS": g1["pass"] and g2["pass"] and g3["pass"] and g4["pass"]})

    (REPORTS / "gate_stage2_verdict.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    passed = [v for v in verdicts if v["PASS"]]
    print("\n" + "=" * 72)
    if passed:
        print("✅ 过四关组合:")
        for v in passed:
            print(f"  {v['label']}  留出期Calmar {v['holdout']['holdout_calmar']} t={v['holdout_t']}")
    else:
        print("❌ 无组合通过加固四关 —— TDX 组合在本仪器下无可确认 edge（如实记录）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
