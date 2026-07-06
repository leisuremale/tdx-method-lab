"""统一证伪关事件引擎：T+1 次日开盘成交 + 涨跌停约束 + 确认窗口 + 冷却。

与 backtest.simulate 的区别（这是给证伪关用的严格版）：
- 信号日 t 收盘确认 → t+1 开盘价成交（不吃信号日收盘）
- t+1 开盘涨停 → 拒买（不追一字）；开盘跌停 → 卖出顺延到首个可卖日
- 入场/退出均为布尔信号数组输入 —— 引擎与具体指标解耦，组合网格只拼数组
"""

from __future__ import annotations

import numpy as np

from tdx_lab.indicators import board_limit_pct


def entry_from_event_confirm(event: np.ndarray, confirm: np.ndarray,
                             window: int) -> np.ndarray:
    """观察事件 + 确认器：事件日后 window 个交易日内首个确认日为入场信号日。

    确认日=入场信号日（成交仍在其次日开盘）。事件日当天满足确认也算。
    """
    n = len(event)
    entry = np.zeros(n, dtype=bool)
    pending_until = -1
    for i in range(n):
        if event[i]:
            pending_until = max(pending_until, i + window)
        if pending_until >= i and confirm[i]:
            entry[i] = True
            pending_until = -1
    return entry


def simulate_events(open_, high, low, close, entry_signal, exit_signal, *,
                    code: str, cost: float = 0.0013, min_hold: int = 0,
                    max_hold: int | None = None, confirm_days: int = 1,
                    cooldown: int = 5,
                    giveback: tuple | None = None) -> dict:
    """单股事件回测（证伪关口径）。

    - entry_signal[t]=True 且空仓且冷却结束 → 于 t+1 开盘买入（开盘涨停则拒买）
    - exit_signal 连续 confirm_days 日为真 且 持有≥min_hold → t+1 开盘卖出
      （开盘跌停顺延）；max_hold 强制退出
    - 返回 equity(起点1.0)、trades、blocked_entries
    """
    o = np.asarray(open_, float)
    c = np.asarray(close, float)
    n = len(c)
    limit = board_limit_pct(code) / 100

    equity = np.ones(n)
    holding = False
    shares = 0.0
    eq = 1.0
    entry_idx = -1
    entry_price = 0.0
    peak_close = 0.0
    cooldown_left = 0
    exit_streak = 0
    pending_exit = False
    trades = []
    blocked = 0

    def limit_up_open(i):
        return o[i] >= round(c[i - 1] * (1 + limit), 2)

    def limit_down_open(i):
        return o[i] <= round(c[i - 1] * (1 - limit), 2)

    pending_entry = False
    for i in range(1, n):
        # ---- 先处理次日执行 ----
        if pending_entry and not holding:
            pending_entry = False
            if limit_up_open(i):
                blocked += 1
            else:
                entry_price = o[i]
                shares = eq * (1 - cost) / entry_price
                holding = True
                entry_idx = i
                exit_streak = 0
                pending_exit = False
                peak_close = entry_price
        elif pending_exit and holding:
            if not limit_down_open(i):
                exit_price = o[i]
                eq = shares * exit_price * (1 - cost)
                holding = False
                pending_exit = False
                cooldown_left = cooldown
                trades.append({"entry_idx": entry_idx, "exit_idx": i,
                               "entry_price": round(entry_price, 4),
                               "exit_price": round(exit_price, 4),
                               "return_pct": round((exit_price / entry_price - 1) * 100
                                                   - cost * 2 * 100, 4),
                               "hold_days": i - entry_idx})
            # 跌停顺延：pending_exit 保持 True

        # ---- 再按当日收盘信号排程明日动作 ----
        if holding and not pending_exit:
            if exit_signal[i]:
                exit_streak += 1
            else:
                exit_streak = 0
            hold_days = i - entry_idx
            gb_hit = False
            if giveback is not None:
                peak_close = max(peak_close, c[i])
                activate, retain = giveback
                peak_gain = peak_close / entry_price - 1
                if peak_gain >= activate and \
                   c[i] <= entry_price * (1 + peak_gain * retain):
                    gb_hit = True  # 利润守护：不受 min_hold 约束
            if gb_hit or (exit_streak >= confirm_days and hold_days >= min_hold) or \
               (max_hold is not None and hold_days >= max_hold):
                pending_exit = True
        elif not holding:
            if cooldown_left > 0:
                cooldown_left -= 1
            elif entry_signal[i] and not pending_entry:
                pending_entry = True

        equity[i] = shares * c[i] if holding else eq

    return {"equity": equity, "trades": trades, "blocked_entries": blocked}
