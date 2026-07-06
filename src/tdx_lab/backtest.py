"""单股事件驱动回测器——基于信号触发买卖，模拟真实交易流程。

设计来源：stock-exchange/harness/stop_policy.py 的 simulate()
改造：入场条件从"首个ATR就绪日"改为"三指标信号触发"
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tdx_lab.indicators import atr


def simulate(
    df: pd.DataFrame,
    xhsub: dict[str, np.ndarray],
    xhmain: dict[str, np.ndarray],
    *,
    entry_rules: str = "tian_ma_only",
    exit_rules: str = "take_profit_or_trend_down",
    cost: float = 0.0013,
    min_hold_days: int = 3,
    max_hold_days: int | None = None,
    confirm_days: int = 2,
    cooldown_days: int = 5,
    atr_window: int = 20,
) -> dict:
    """单股信号驱动回测模拟。

    Args:
        df: 行情 DataFrame（含 open/high/low/close/volume/date）
        xhsub: compute_xhsub() 输出
        xhmain: compute_xhmain() 输出
        entry_rules: 入场规则集
            - "tian_ma_only": 只在天马日入场
            - "tian_ma_trend_state": 天马 + 主图趋势在强势区 + 观变上升
            - "tian_ma_or_trend": 天马 或 趋势转强
            - "tian_ma_or_var11": 天马 或 多空金叉
        exit_rules: 退出规则集
            - "take_profit_or_trend_down": 止盈 或 趋势转弱
            - "take_profit_only": 仅止盈
            - "trend_down_only": 仅趋势转弱
            - "zhz_break_only": MACD 跌破零轴
            - "all": 止盈 + 趋势转弱 + MACD破零
        cost: 单边交易成本（买入/卖出各扣一次）
        max_hold_days: 最大持仓天数，超时强制退出
        cooldown_days: 退出后冷却天数，期间不重新入场
        atr_window: ATR 计算窗口

    Returns:
        {
            equity:        np.ndarray 每日权益序列（未持仓=现金不变）
            trades:        list[dict] 每笔交易明细
            daily_state:   np.ndarray 每日状态 (0=空仓, 1=持仓)
            entry_signals: int 入场信号触发次数
            exit_signals:  int 退出信号触发次数
            total_return:  float 总收益率
            max_drawdown:  float 最大回撤
            win_rate:      float 胜率
            avg_return:    float 平均每笔收益
            avg_hold_days: float 平均持仓天数
            calmar:        float Calmar比率
        }
    """
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    v = df["volume"].values
    dates = df["date"].values
    n = len(c)

    a = atr(h, l, c, atr_window)

    # ── 入场条件函数 ──
    def can_entry(i: int) -> bool:
        if i < 34:
            return False
        tm = bool(xhsub["tian_ma"][i])
        tu = bool(xhmain["trend_up"][i])
        v11 = bool(xhmain["var11"][i])
        sr = bool(xhmain["strong_reversal"][i])
        hold_now = xhsub["guan_bian"][i] >= xhsub["guan_bian"][i - 1]
        trend_state = (
            np.isfinite(xhmain["cxhzb"][i])
            and np.isfinite(xhmain["gzz"][i])
            and xhmain["cxhzb"][i] >= xhmain["gzz"][i]
        )
        zhz_improving = xhsub["zhz"][i] >= xhsub["zhz"][i - 1]

        if entry_rules == "tian_ma_only":
            return tm
        elif entry_rules in {"tian_ma_trend_state", "tian_ma_and_trend"}:
            # V2: 天马 + 主图趋势在强势区 + 观变上升
            return tm and trend_state and hold_now
        elif entry_rules == "tian_ma_or_trend":
            return tm or tu or v11
        elif entry_rules == "tian_ma_or_var11":
            return tm or v11
        elif entry_rules == "trend_up_only":
            return tu and hold_now and zhz_improving
        elif entry_rules == "var11_only":
            return v11 and hold_now
        raise ValueError(f"unknown entry_rules: {entry_rules}")

    # ── 退出条件函数 ──
    def can_exit(i: int) -> bool:
        if i < 34:
            return False
        tp = xhsub["guan_bian"][i] < xhsub["guan_bian"][i - 1]
        td = bool(xhmain["trend_down"][i])
        zb = xhsub["zhz"][i] < 0 and xhsub["zhz"][i - 1] >= 0
        ps = xhsub["zhz"][i] >= 0 and xhsub["zhz"][i] < xhsub["zhz"][i - 1]

        if exit_rules == "take_profit_or_trend_down":
            return tp or td
        elif exit_rules == "take_profit_only":
            return tp
        elif exit_rules == "trend_down_only":
            return td
        elif exit_rules == "zhz_break_only":
            return zb
        elif exit_rules == "all":
            return tp or td or zb or ps
        raise ValueError(f"unknown exit_rules: {exit_rules}")

    # ── 模拟循环 ──
    equity = np.ones(n)
    daily_state = np.zeros(n, dtype=int)
    cooldown_left = 0
    holding = False
    entry_idx = 0
    entry_price = 0.0
    shares = 0.0
    exit_signal_days = 0  # 连续退出信号天数

    trades = []
    entry_count = 0
    exit_count = 0

    for i in range(34, n):
        if holding:
            # 连续确认：需要连续 N 天退出信号才真正退出（过滤单日噪声）
            if can_exit(i):
                exit_signal_days += 1
            else:
                exit_signal_days = 0

            hold_days = i - entry_idx
            exit_confirmed = exit_signal_days >= confirm_days
            must_exit = (exit_confirmed and hold_days >= min_hold_days)
            if max_hold_days and hold_days >= max_hold_days:
                must_exit = True

            if must_exit:
                exit_price = min(o[i], c[i])
                equity[i] = shares * exit_price * (1 - cost)
                holding = False
                cooldown_left = cooldown_days
                exit_count += 1
                exit_signal_days = 0

                ret = (exit_price / entry_price - 1) * 100
                reason = "max_hold" if (max_hold_days and hold_days >= max_hold_days) else "signal"
                trades.append({
                    "entry_date": dates[entry_idx],
                    "exit_date": dates[i],
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "return_pct": round(ret, 2),
                    "hold_days": hold_days,
                    "exit_reason": reason,
                })
            else:
                equity[i] = shares * c[i]
        else:
            # 空仓/冷却期
            equity[i] = equity[i - 1]  # 现金不动
            if cooldown_left > 0:
                cooldown_left -= 1
            elif can_entry(i):
                # 入场：当日收盘价
                entry_price = c[i]
                shares = equity[i - 1] * (1 - cost) / entry_price
                equity[i] = shares * entry_price
                holding = True
                entry_idx = i
                entry_count += 1
                exit_signal_days = 0
            else:
                equity[i] = equity[i - 1]

        daily_state[i] = int(holding)

    # ── 绩效统计 ──
    eq = equity[34:]  # 只算有效区间
    total_return = (eq[-1] - 1.0) * 100
    peak = np.maximum.accumulate(eq)
    dd = (eq / peak - 1.0) * 100
    max_drawdown = float(np.min(dd))
    if not trades:
        calmar = 0.0
    elif max_drawdown < 0:
        calmar = total_return / abs(max_drawdown)
    else:
        calmar = float("inf")

    if trades:
        wins = sum(1 for t in trades if t["return_pct"] > 0)
        win_rate = wins / len(trades) * 100
        avg_return = np.mean([t["return_pct"] for t in trades])
        avg_hold_days = np.mean([t["hold_days"] for t in trades])
    else:
        win_rate = 0.0
        avg_return = 0.0
        avg_hold_days = 0.0

    return {
        "equity": equity,
        "trades": trades,
        "daily_state": daily_state,
        "entry_signals": entry_count,
        "exit_signals": exit_count,
        "total_return": round(total_return, 2),
        "max_drawdown": round(max_drawdown, 2),
        "win_rate": round(win_rate, 2),
        "avg_return": round(avg_return, 2),
        "avg_hold_days": round(avg_hold_days, 1),
        "calmar": round(calmar, 2),
        "n_trades": len(trades),
    }


def benchmark_buy_hold(df: pd.DataFrame, cost: float = 0.0013) -> dict:
    """买入持有基准（入场=第34日收盘，出场=最后一日收盘）。"""
    c = df["close"].values
    entry = c[34]
    exit_price = c[-1]
    ret = (exit_price / entry - 1) * 100 - cost * 200  # 双边成本

    # 路径回撤
    seg = c[34:] / c[34]
    peak = np.maximum.accumulate(seg)
    dd = float(np.min(seg / peak - 1) * 100)
    calmar = ret / abs(dd) if dd < 0 else float("inf")

    return {
        "total_return": round(ret, 2),
        "max_drawdown": round(dd, 2),
        "calmar": round(calmar, 2),
        "n_trades": 1,
    }


def compare_rules(
    df: pd.DataFrame,
    xhsub: dict,
    xhmain: dict,
    entry_rules_list: list[str],
    exit_rules_list: list[str],
    cost: float = 0.0013,
) -> pd.DataFrame:
    """批量比较不同入场/退出规则组合的绩效。

    Returns:
        DataFrame with columns: entry_rule, exit_rule, n_trades, total_return,
        max_drawdown, win_rate, avg_return, avg_hold_days, calmar
    """
    results = []
    for entry in entry_rules_list:
        for exit_ in exit_rules_list:
            r = simulate(df, xhsub, xhmain, entry_rules=entry, exit_rules=exit_, cost=cost)
            results.append({
                "entry_rule": entry,
                "exit_rule": exit_,
                "n_trades": r["n_trades"],
                "total_return": r["total_return"],
                "max_drawdown": r["max_drawdown"],
                "win_rate": r["win_rate"],
                "avg_return": r["avg_return"],
                "avg_hold_days": r["avg_hold_days"],
                "calmar": r["calmar"],
            })

    # 加入买入持有基准
    bh = benchmark_buy_hold(df, cost)
    results.append({
        "entry_rule": "buy_hold",
        "exit_rule": "buy_hold",
        "n_trades": bh["n_trades"],
        "total_return": bh["total_return"],
        "max_drawdown": bh["max_drawdown"],
        "win_rate": 100.0 if bh["total_return"] > 0 else 0.0,
        "avg_return": bh["total_return"],
        "avg_hold_days": len(df) - 34,
        "calmar": bh["calmar"],
    })

    out = pd.DataFrame(results)
    out["_rank_active"] = (out["n_trades"] > 0).astype(int)
    out = out.sort_values(
        ["_rank_active", "calmar", "total_return"],
        ascending=[False, False, False],
    )
    return out.drop(columns=["_rank_active"])
