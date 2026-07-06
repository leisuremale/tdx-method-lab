# -*- coding: utf-8 -*-
"""预注册第三轮：同日合取入场 × 投票制退出——用户指定的复杂组合形态补测。

与已测的区别：入场是"事件∧当日状态"（过滤式），非"事件→等N日确认"（延迟式）；
退出是"多线投票(状态型,避开cross+confirm_days陷阱)"，非单线。
验收（跑前写死）：留出期 Calmar > 2.105(V-final) 且 t≥2 且 > 对应孪生；
本轮 14 格，对同一留出期累计第三轮挖掘——结果无论好坏全公布。
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
from unified_gate_stage2 import HOLDOUT_START, clustered_t, run


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    GS.worker_init()

    # 每股补充当日状态数组
    for s in GS._G["stocks"]:
        c = s["c"]
        # 从缓存重取 volume（worker_init 未保存）
        prefix = "sh." if s["code"].startswith(("6", "9")) else "sz."
        raw = pd.read_csv(GS.CACHE / f"{prefix}{s['code']}.csv")
        vol = raw["volume"].values.astype(float)[-len(c):]
        ema10 = pd.Series(c).ewm(span=10, adjust=False).mean().values
        ma55 = pd.Series(c).rolling(55).mean().values
        vma20 = pd.Series(vol).rolling(20).mean().values
        sub_holdline = ~s["exits"]["guanbian_dn"]          # 观变上升
        ema12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
        ema26 = pd.Series(c).ewm(span=26, adjust=False).mean().values
        clz = (ema26 - ema12) * -1
        xhx = pd.Series(clz).ewm(span=9, adjust=False).mean().values
        zhz = 2 * (clz - xhx)
        zhz_imp = np.zeros(len(c), bool)
        zhz_imp[1:] = zhz[1:] >= zhz[:-1]
        s["st"] = {
            "holdline": sub_holdline,
            "zhz_imp": zhz_imp,
            "above_ma55": c > np.nan_to_num(ma55, nan=np.inf),
            "below_ma55": c < np.nan_to_num(ma55, nan=-np.inf),
            "vol_dry": vol < np.nan_to_num(vma20, nan=np.inf),
            "muma": c > ema10,
        }
        # 投票退出（状态型）：观变跌 / 牧马破 / 操盘失守
        ema15 = pd.Series(c).ewm(span=15, adjust=False).mean().values
        bad1 = s["exits"]["guanbian_dn"]
        bad2 = c < ema10
        bad3 = ~((c >= ema15) & (ema10 > ema15))
        votes = bad1.astype(int) + bad2.astype(int) + bad3.astype(int)
        s["exits"]["vote2of3"] = votes >= 2
        s["exits"]["vote3of3"] = votes >= 3

    base = {"event": "tm21_15", "confirm": "none", "exit": "hold30",
            "min_hold": 0, "filter": "none"}

    def run_with_entry_state(state_key, label, exit_cfg=None):
        cfg = dict(base)
        if exit_cfg:
            cfg.update(exit_cfg)
        overrides = []
        for s in GS._G["stocks"]:
            entry = s["events"]["tm21_15"] & s["entry_ok"]
            if state_key:
                entry = entry & s["st"][state_key]
            overrides.append(entry)
        m, hc, trades = run(cfg, entry_overrides=overrides, collect=True)
        t_h, _ = clustered_t(trades, start=HOLDOUT_START)
        print(f"{label:<30}{m['holdout_calmar']:>10}{t_h:>8.2f}{sum(hc):>8}")
        return {"label": label, "hold_calmar": m["holdout_calmar"],
                "hold_t": round(t_h, 2), "hold_trades": sum(hc)}

    print(f"{'变体':<30}{'留出Calmar':>10}{'留出t':>8}{'留出成交':>8}")
    rows = []
    # A. 合取入场族（退出=hold30 固定）
    for key, label in [(None, "V-final基线(tm21_15+hold30)"),
                       ("holdline", "∧观变上升"), ("zhz_imp", "∧MACD柱修复"),
                       ("above_ma55", "∧MA55上方(趋势中回调)"),
                       ("below_ma55", "∧MA55下方(深熊反弹)"),
                       ("vol_dry", "∧缩量"), ("muma", "∧牧马上方")]:
        rows.append(run_with_entry_state(key, label))
    # 双重合取
    for k1, k2, label in [("holdline", "zhz_imp", "∧观变上升∧MACD修复"),
                          ("above_ma55", "vol_dry", "∧MA55上∧缩量")]:
        for s in GS._G["stocks"]:
            s["st"]["_tmp"] = s["st"][k1] & s["st"][k2]
        rows.append(run_with_entry_state("_tmp", label))
    # B. 投票制退出族（入场=纯 tm21_15）
    for ex, mh, label in [("vote2of3", 0, "投票2/3退出(无地板)"),
                          ("vote2of3", 20, "投票2/3退出+20天地板"),
                          ("vote2of3", 30, "投票2/3退出+30天地板"),
                          ("vote3of3", 20, "投票3/3退出+20天地板"),
                          ("vote3of3", 30, "投票3/3退出+30天地板")]:
        rows.append(run_with_entry_state(None, label,
                                         exit_cfg={"exit": ex, "min_hold": mh}))

    pd.DataFrame(rows).to_csv(GS.REPORTS / "rescue2_conjunctions.csv",
                              index=False, encoding="utf-8-sig")
    print("\n预注册判定线：Calmar>2.105 且 t>=2 且 优于孪生")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
