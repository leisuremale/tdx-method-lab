"""统一证伪关事件引擎测试：T+1 开盘成交、涨跌停约束、确认窗口、冷却。"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tdx_lab.event_engine import simulate_events  # noqa: E402


def flat(n, price=100.0):
    o = np.full(n, price); h = o + 0.5; l = o - 0.5; c = o.copy()
    return o, h, l, c


def test_entry_executes_next_open_not_signal_close():
    o, h, l, c = flat(10)
    o[6] = 102.0  # 信号日=5，次日开盘 102 成交
    entry = np.zeros(10, bool); entry[5] = True
    exit_ = np.zeros(10, bool); exit_[8] = True   # 8 日信号 → 9 日开盘出
    r = simulate_events(o, h, l, c, entry, exit_, code="000001", cost=0.0)
    assert len(r["trades"]) == 1
    t = r["trades"][0]
    assert t["entry_idx"] == 6 and t["entry_price"] == 102.0
    assert t["exit_idx"] == 9 and t["exit_price"] == o[9]


def test_limit_up_open_blocks_entry():
    o, h, l, c = flat(10)
    c[5] = 100.0
    o[6] = 110.0  # 次日开盘一字涨停(主板10%) → 拒买，信号作废
    entry = np.zeros(10, bool); entry[5] = True
    r = simulate_events(o, h, l, c, entry, np.zeros(10, bool), code="600000", cost=0.0)
    assert r["trades"] == [] and r["blocked_entries"] == 1


def test_limit_down_open_defers_exit():
    o, h, l, c = flat(12)
    entry = np.zeros(12, bool); entry[2] = True     # 3 日开盘入场
    exit_ = np.zeros(12, bool); exit_[5] = True     # 6 日开盘想出
    c[5] = 100.0
    o[6] = 90.0    # 6 日开盘跌停 → 顺延
    c[6] = 90.0
    o[7] = 91.0    # 7 日开盘可出
    r = simulate_events(o, h, l, c, entry, exit_, code="600000", cost=0.0)
    assert len(r["trades"]) == 1
    assert r["trades"][0]["exit_idx"] == 7 and r["trades"][0]["exit_price"] == 91.0


def test_min_hold_blocks_early_exit_and_cooldown_blocks_reentry():
    o, h, l, c = flat(30)
    entry = np.zeros(30, bool); entry[2] = True; entry[12] = True
    exit_ = np.zeros(30, bool); exit_[5] = True; exit_[20] = True
    r = simulate_events(o, h, l, c, entry, exit_, code="000001",
                        cost=0.0, min_hold=10, cooldown=10)
    # 第一笔：5日信号被 min_hold=10 拦下，20日信号生效 → 21日开盘出（持有18日）
    assert len(r["trades"]) == 1
    assert r["trades"][0]["exit_idx"] == 21
    # 12 日的第二个入场信号发生在持仓中 → 忽略；出场后无后续信号


def test_confirm_window_entry():
    # 事件在 3 日，确认条件 7 日才满足（窗口内）→ 8 日开盘成交
    o, h, l, c = flat(15)
    event = np.zeros(15, bool); event[3] = True
    confirm = np.zeros(15, bool); confirm[7:] = True
    from tdx_lab.event_engine import entry_from_event_confirm
    entry = entry_from_event_confirm(event, confirm, window=10)
    assert entry[7] and entry.sum() == 1
    # 窗口外不确认
    entry2 = entry_from_event_confirm(event, confirm, window=3)
    assert entry2.sum() == 0


def test_costs_applied_both_sides():
    o, h, l, c = flat(10)
    entry = np.zeros(10, bool); entry[2] = True
    exit_ = np.zeros(10, bool); exit_[6] = True
    r = simulate_events(o, h, l, c, entry, exit_, code="000001", cost=0.0013)
    eq_end = r["equity"][-1]
    assert eq_end == pytest.approx((1 - 0.0013) * (1 - 0.0013), rel=1e-9)
