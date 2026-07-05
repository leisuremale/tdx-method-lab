"""信号事件表生成——从指标数组转为结构化信号事件。

信号字典（与 docs/methodology/tdx-three-indicator-test-plan.md 一致）：
- tian_ma        天马（低位启动）    入场候选
- trend_up       趋势转强 CXHZB↑    入场候选
- trend_down     趋势转弱 CXHZB↓    退出候选
- strong_reversal 强势反包 TJ       入场候选
- var11          多空金叉            入场候选
- hold           持股（观变上升）    持仓确认
- take_profit    止盈（观变下降）    止盈观察
- macd_positive_shrink  MACD正柱收缩 止盈观察
- macd_negative_break   MACD破零     强退出
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# 信号名 → (来源, 类型, 用途)
SIGNAL_REGISTRY = {
    "tian_ma":               ("副图", "入场候选", "天马低位金叉"),
    "trend_up":              ("主图", "入场候选", "CXHZB上穿GZZ"),
    "trend_down":            ("主图", "退出候选", "CXHZB下穿GZZ"),
    "strong_reversal":       ("主图", "入场候选", "强势反包TJ"),
    "var11":                 ("主图", "入场候选", "多周期EMA金叉"),
    "hold":                  ("副图", "持仓确认", "观变持续上升"),
    "take_profit":           ("副图", "止盈观察", "观变开始下降"),
    "macd_positive_shrink":  ("副图", "止盈观察", "MACD正柱收缩"),
    "macd_negative_break":   ("副图", "强退出",   "MACD柱体跌破零轴"),
    "water_extreme":         ("水深", "退出辅助", "水深120日极端分位"),
    "water_turn":            ("水深", "退出辅助", "水深3日方向拐头"),
}


def generate_signal_table(
    df: pd.DataFrame,
    xhsub: dict[str, np.ndarray],
    xhmain: dict[str, np.ndarray],
    xhwater: dict[str, np.ndarray] | None = None,
) -> pd.DataFrame:
    """从指标数组生成信号事件表。

    Args:
        df:      含 date/open/high/low/close/volume 的行情 DataFrame
        xhsub:   compute_xhsub() 的输出
        xhmain:  compute_xhmain() 的输出
        xhwater: compute_xhwater() 的输出（可选）

    Returns:
        每行一个信号事件的 DataFrame:
        date, close, signal_name, signal_type, signal_use, value
    """
    n = len(df)
    c = df["close"].values

    events = []

    def _emit(date, price, name, value=None):
        meta = SIGNAL_REGISTRY.get(name, ("?", "?", "?"))
        events.append({
            "date": date,
            "close": round(price, 2),
            "signal_name": name,
            "signal_type": meta[0],
            "signal_use": meta[1],
            "signal_desc": meta[2],
            "value": round(value, 2) if value is not None else None,
        })

    for i in range(34, n):  # 跳过计算窗口
        d = df["date"].iloc[i]
        price = c[i]

        # XHSUB 副图信号
        if xhsub["tian_ma"][i]:
            _emit(d, price, "tian_ma", xhsub["az3"][i])

        if xhsub["guan_bian"][i] >= xhsub["guan_bian"][i - 1]:
            _emit(d, price, "hold")
        else:
            _emit(d, price, "take_profit")

        zhz = xhsub["zhz"]
        if zhz[i] >= 0 and zhz[i] < zhz[i - 1]:
            _emit(d, price, "macd_positive_shrink", zhz[i])
        if zhz[i - 1] >= 0 > zhz[i]:
            _emit(d, price, "macd_negative_break", zhz[i])

        # XHMAIN 主图信号
        if xhmain["trend_up"][i]:
            _emit(d, price, "trend_up")
        if xhmain["trend_down"][i]:
            _emit(d, price, "trend_down")
        if xhmain["strong_reversal"][i]:
            _emit(d, price, "strong_reversal")
        if xhmain["var11"][i]:
            _emit(d, price, "var11")

        # XHWATER 水深信号
        if xhwater is not None:
            wz = xhwater.get("water_zscore_120", np.full(n, np.nan))
            ws = xhwater.get("water_slope_3", np.full(n, np.nan))
            if not np.isnan(wz[i]) and abs(wz[i]) > 2.0:
                _emit(d, price, "water_extreme", wz[i])
            if i >= 4 and not np.isnan(ws[i]) and not np.isnan(ws[i - 1]):
                if ws[i] * ws[i - 1] < 0:
                    _emit(d, price, "water_turn", ws[i])

    return pd.DataFrame(events)


def filter_entry_signals(signal_df: pd.DataFrame) -> pd.DataFrame:
    """只取入场候选信号。"""
    return signal_df[signal_df["signal_use"] == "入场候选"]


def filter_exit_signals(signal_df: pd.DataFrame) -> pd.DataFrame:
    """取退出候选 + 强退出 + 止盈观察信号。"""
    return signal_df[signal_df["signal_use"].isin(["退出候选", "强退出", "止盈观察"])]


def daily_state(df: pd.DataFrame, xhsub: dict, xhmain: dict) -> pd.DataFrame:
    """生成每日状态表（每个交易日一行，包含所有状态标签）。

    用于回测时判断每日持仓状态。
    """
    n = len(df)
    records = []
    for i in range(34, n):
        guan_bian = xhsub["guan_bian"]
        zhz = xhsub["zhz"]
        macd_state = xhsub["macd_state"]
        records.append({
            "date": df["date"].iloc[i],
            "close": round(df["close"].iloc[i], 2),
            "tian_ma": int(xhsub["tian_ma"][i]),
            "hold": int(guan_bian[i] >= guan_bian[i - 1]),
            "take_profit": int(guan_bian[i] < guan_bian[i - 1]),
            "zhz": round(zhz[i], 2),
            "macd_state": macd_state[i],
            "az3": round(xhsub["az3"][i], 1),
            "cxhzb_above_gzz": int(
                np.isfinite(xhmain["cxhzb"][i])
                and np.isfinite(xhmain["gzz"][i])
                and xhmain["cxhzb"][i] >= xhmain["gzz"][i]
            ),
            "trend_up": int(xhmain["trend_up"][i]),
            "trend_down": int(xhmain["trend_down"][i]),
            "var11": int(xhmain["var11"][i]),
            "strong_reversal": int(xhmain["strong_reversal"][i]),
        })
    return pd.DataFrame(records)
