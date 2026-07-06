"""Initialize paper-trading log from the current V1 action list."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_operational_system import main as build_operational_system


def main() -> int:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    build_operational_system()
    actions = pd.read_csv(reports / "v1_current_action_list.csv", dtype={"code": str})
    selected = actions[actions["action"].isin(["entry_candidate", "exit_condition"])].copy()
    selected.insert(0, "paper_id", [f"P{idx + 1:04d}" for idx in range(len(selected))])
    selected["paper_status"] = "open_for_manual_review"
    selected["planned_action"] = selected["action"].map(
        {"entry_candidate": "buy_watch", "exit_condition": "sell_or_reduce_watch"}
    )
    selected["manual_decision"] = ""
    selected["decision_reason"] = ""
    selected["paper_entry_price"] = ""
    selected["paper_exit_price"] = ""
    selected["paper_result_pct"] = ""
    selected["review_after_date"] = ""
    selected["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S %z")

    columns = [
        "paper_id",
        "created_at",
        "code",
        "name",
        "segment",
        "policy",
        "planned_action",
        "paper_status",
        "date",
        "close",
        "reason",
        "current_state",
        "basket_bull",
        "basket_down",
        "manual_decision",
        "decision_reason",
        "paper_entry_price",
        "paper_exit_price",
        "paper_result_pct",
        "review_after_date",
    ]
    selected[columns].to_csv(reports / "v1_paper_trading_log.csv", index=False)
    print(f"paper_events={len(selected)}")
    print(reports / "v1_paper_trading_log.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
