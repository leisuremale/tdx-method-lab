# -*- coding: utf-8 -*-
"""预注册补测：混合退出（固定持有地板 + 趋势线延长）能否救回副图/主图退出线。

诚实声明：第二轮挖掘。验收（预注册，跑前写死）：
- 变体须在留出期同时满足：t≥2 且 Calmar > V-final(2.105) 且 Calmar > 其固定持有孪生
- 若走置换关：Bonferroni 收紧至 99.64 分位（累计 14 个候选对同一留出期）
家族（15格）：entry=tm21_15 固定；min_hold∈{30,40}×延长退出{观变转跌,趋势转弱,
牧马转弱,操盘线失守,v1组合}=10 + 固定持有孪生 hold{30,40,50} + 全期基线记录。
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

    # 给每只股补两个退出数组：牧马转弱 / 操盘线失守
    from tdx_lab.indicators import compute_xhmain
    for s in GS._G["stocks"]:
        # mu_ma / cao_pan 已在 events 预计算里？没有——从主图重算成本高；用价格重构
        c = s["c"]
        ema10 = pd.Series(c).ewm(span=10, adjust=False).mean().values
        ema15 = pd.Series(c).ewm(span=15, adjust=False).mean().values
        s["exits"]["muma_off"] = c < ema10
        s["exits"]["caopan_off"] = ~((c >= ema15) & (ema10 > ema15))

    variants = []
    for mh in (30, 40):
        for ex in ("guanbian_dn", "trend_dn", "muma_off", "caopan_off", "v1_tp_or_td"):
            variants.append({"event": "tm21_15", "confirm": "none", "exit": ex,
                             "min_hold": mh, "filter": "none", "label": f"mh{mh}+{ex}"})
    for hb in (30, 40, 50):
        variants.append({"event": "tm21_15", "confirm": "none", "exit": f"hold{hb}",
                         "min_hold": 0, "filter": "none", "label": f"固定hold{hb}"})
        if f"hold{hb}" not in ("hold10", "hold20", "hold30"):
            pass  # hold40/50 走 max_hold 分支：exit 名 holdNN 由 sim() 解析

    print(f"{'变体':<24}{'留出Calmar':>10}{'留出t':>8}{'留出成交':>8}  发现期Calmar")
    rows = []
    for v in variants:
        m, hold_counts, trades = run(v, collect=True)
        t_h, k = clustered_t(trades, start=HOLDOUT_START)
        # 发现期指标
        disc_trades = [t for t in trades if t["entry_date"] < HOLDOUT_START]
        t_d, _ = clustered_t(disc_trades)
        rows.append({**v, "hold_calmar": m["holdout_calmar"], "hold_t": round(t_h, 2),
                     "hold_trades": sum(hold_counts)})
        print(f"{v['label']:<24}{m['holdout_calmar']:>10}{t_h:>8.2f}{sum(hold_counts):>8}"
              f"  (t_disc={t_d:.2f})")

    df = pd.DataFrame(rows)
    df.to_csv(GS.REPORTS / "rescue_exits_test.csv", index=False, encoding="utf-8-sig")
    print("\n预注册判定：延长变体须 同时 > V-final(2.105) 且 > 其固定持有孪生，且 t>=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
