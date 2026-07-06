# -*- coding: utf-8 -*-
"""P1 附属：席位数敏感性（5席/20%上限 vs 3席/30%上限），随机规则 300 种子分布。"""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(LAB / "scripts"))

import numpy as np

import gate_sweep as GS
import slot_portfolio as SP


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    GS.worker_init()
    master, events, by_day = SP.build_event_table()
    for slots, cap in ((3, 0.30), (5, 0.20), (8, 0.125)):
        SP.SEAT_CAP = cap
        rc, dd = [], []
        for seed in range(300):
            eq, n_tr, occ = SP.simulate_account(master, by_day, "random", seed,
                                                slots=slots)
            m = SP.metrics(eq, master, SP.HOLDOUT)
            rc.append(m["calmar"])
            dd.append(m["maxdd"])
        rc, dd = np.array(rc), np.array(dd)
        print(f"{slots}席/{cap:.0%}上限: 留出Calmar 中位 {np.median(rc):.3f} "
              f"[p5 {np.percentile(rc,5):.3f}, p95 {np.percentile(rc,95):.3f}] "
              f"MaxDD 中位 {np.median(dd):.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
