"""三指标公式计算——纯 Python 复现通达信 XHMAIN/XHSUB/XHWATER 核心逻辑。

不含 XMA(未来函数)、WINNER/COST(通达信专有) —— 这些只能通过 TdxQuant 获取。
回测时不使用含未来函数的信号（如趋顶/趋底）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma_tdx(x: np.ndarray, n: int, m: int) -> np.ndarray:
    """通达信 SMA 函数: SMA(X, N, M) = (M*X + (N-M)*SMA')/N"""
    result = np.full_like(x, np.nan, dtype=float)
    start = 0
    while start < len(x) and not np.isfinite(x[start]):
        start += 1
    if start >= len(x):
        return result
    result[start] = x[start]
    for i in range(start + 1, len(x)):
        if not np.isfinite(x[i]):
            result[i] = result[i - 1]
        else:
            result[i] = (m * x[i] + (n - m) * result[i - 1]) / n
    return result


# ═══════════════════════════════════════════════════════════════
# XHSUB 副图指标
# ═══════════════════════════════════════════════════════════════

def compute_xhsub(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """
    计算 XHSUB 副图全部指标。

    Args:
        df: 含 open/high/low/close/volume 列的 DataFrame

    Returns:
        dict with keys: zhz, guan_bian, tian_ma, az3, macd_state
        所有数组长度 = len(df)
    """
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    n = len(c)

    # ── MACD 变体 ──
    ema12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(c).ewm(span=26, adjust=False).mean().values
    clz = (ema26 - ema12) * -1  # MX-KX then *-1
    xhx = pd.Series(clz).ewm(span=9, adjust=False).mean().values
    zhz = 2 * (clz - xhx)  # MACD 柱体

    # ── 观变 ──
    yscz = ema12 - ema26
    dqph = pd.Series(yscz).ewm(span=1, adjust=False).mean().values
    zqph = pd.Series(dqph).ewm(span=5, adjust=False).mean().values
    guan_bian = (dqph + zqph) / 2

    # ── MACD 状态分类 ──
    macd_state = np.full(n, "", dtype=object)
    for i in range(1, n):
        if zhz[i] >= 0 and zhz[i] >= zhz[i - 1]:
            macd_state[i] = "red_up"     # 红柱扩张
        elif zhz[i] >= 0 and zhz[i] < zhz[i - 1]:
            macd_state[i] = "purple_dn"  # 紫柱收缩
        elif zhz[i] < 0 and zhz[i] >= zhz[i - 1]:
            macd_state[i] = "yellow_up"  # 黄柱修复
        else:
            macd_state[i] = "green_dn"   # 绿柱恶化

    # ── 天马：慢速KDJ(34周期)低位金叉 ──
    llv34 = pd.Series(l).rolling(34).min().values
    hhv34 = pd.Series(h).rolling(34).max().values
    az1 = np.where(
        hhv34 != llv34,
        (c - llv34) / (hhv34 - llv34) * 100,
        50.0,
    )
    az2 = sma_tdx(az1, 3, 1)
    az3 = sma_tdx(az2, 3, 1)
    az4 = sma_tdx(az3, 3, 1)

    tian_ma = np.zeros(n, dtype=bool)
    for i in range(35, n):
        tian_ma[i] = (
            az3[i] > az4[i]
            and az3[i - 1] <= az4[i - 1]
            and az3[i] < 20
        )

    return {
        "zhz": zhz,
        "guan_bian": guan_bian,
        "tian_ma": tian_ma,
        "az3": az3,
        "az4": az4,
        "macd_state": macd_state,
    }


# ═══════════════════════════════════════════════════════════════
# XHMAIN 主图指标
# ═══════════════════════════════════════════════════════════════

def compute_xhmain(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """
    计算 XHMAIN 主图核心信号（不含 XMA 未来函数通道）。

    返回: cxhzb, gzz, trend_up, trend_down, var11, strong_reversal
    """
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    o = df["open"].values
    v = df["volume"].values
    n = len(c)

    # ── CXHZB: 加权均价趋势线 ──
    da = (3 * c + o + l + h) / 6
    w = np.array([20, 19, 18, 17, 16, 15, 14, 13, 12, 11,
                  10, 9, 8, 7, 6, 5, 4, 3, 2, 1], dtype=float)
    cxhzb = np.full(n, np.nan)
    for i in range(19, n):
        valid_w = w[: min(20, i + 1)]
        valid_da = da[i - len(valid_w) + 1 : i + 1]
        cxhzb[i] = np.average(valid_da, weights=valid_w)

    # ── GZZ: CXHZB 的 5 日简单平均 ──
    gzz = pd.Series(cxhzb).rolling(5).mean().values

    # ── 趋势转强/转弱 ──
    trend_up = np.zeros(n, dtype=bool)
    trend_down = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if np.isfinite(cxhzb[i]) and np.isfinite(gzz[i]):
            trend_up[i] = (cxhzb[i] > gzz[i]) and (cxhzb[i - 1] <= gzz[i - 1])
            trend_down[i] = (cxhzb[i] < gzz[i]) and (cxhzb[i - 1] >= gzz[i - 1])

    # ── VAR11: 多周期 EMA 金叉 ──
    var10 = c
    duo = (
        pd.Series(var10).ewm(span=7, adjust=False).mean()
        + pd.Series(var10).ewm(span=13, adjust=False).mean()
        + pd.Series(var10).ewm(span=21, adjust=False).mean()
        + pd.Series(var10).ewm(span=34, adjust=False).mean()
    ) / 4
    kong = pd.Series(duo).ewm(span=10, adjust=False).mean()
    var11 = np.zeros(n, dtype=bool)
    for i in range(1, n):
        var11[i] = (duo[i] > kong[i]) and (duo[i - 1] <= kong[i - 1])

    # ── 强势反包 TJ ──
    ma10 = pd.Series(c).rolling(10).mean().values
    strong_reversal = np.zeros(n, dtype=bool)
    for i in range(2, n):
        prev_red = c[i - 1] < o[i - 1]            # 前日阴线
        vol_expand = v[i - 1] > v[i - 2]           # 前日放量
        break_high = c[i] > h[i - 1]               # 今日突破前高
        above_ma10 = c[i] > ma10[i]                # 站上10日线
        strong_reversal[i] = prev_red and vol_expand and break_high and above_ma10

    return {
        "cxhzb": cxhzb,
        "gzz": gzz,
        "trend_up": trend_up,
        "trend_down": trend_down,
        "var11": var11,
        "strong_reversal": strong_reversal,
    }


# ═══════════════════════════════════════════════════════════════
# XHWATER 水深指标（辅助退出）
# ═══════════════════════════════════════════════════════════════

def compute_xhwater(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """
    计算 XHWATER 水深。

    注意：原始公式含 WINNER/COST（通达信专有函数），这里只实现可复现部分。
    水深不直接用于买卖决策，仅作为辅助退出确认器。

    返回: water_raw, water_zscore_120, water_slope_3
    """
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    v = df["volume"].values
    n = len(c)

    # ── 简化水深（DOM = 无 WINNER/COST 版本）──
    # 原始公式过于复杂且有价格阈值 bug，这里用 DOM 归一化版本:
    # 本质是价格相对于 55 日高低区间的相对位置 × 波动加权
    ema55 = pd.Series(c).ewm(span=55, adjust=False).mean().values
    vol55 = pd.Series(v).rolling(55).sum().values

    # DMA: 每日权重 = volume / sum(vol,55)
    dma_val = np.full(n, np.nan)
    dma_val[54] = ema55[54]
    for i in range(55, n):
        if vol55[i] > 0:
            alpha = v[i] / vol55[i]
            dma_val[i] = alpha * ema55[i] + (1 - alpha) * dma_val[i - 1]

    water_raw = dma_val  # 简化版水深

    # ── 派生指标 ──
    # z-score (120日)
    water_zscore_120 = np.full(n, np.nan)
    for i in range(120, n):
        seg = water_raw[i - 119 : i + 1]
        m = np.nanmean(seg)
        s = np.nanstd(seg)
        if s and s > 0:
            water_zscore_120[i] = (water_raw[i] - m) / s

    # 3 日斜率
    water_slope_3 = np.full(n, np.nan)
    for i in range(3, n):
        valid = water_raw[i - 3 : i + 1]
        if not np.any(np.isnan(valid)):
            water_slope_3[i] = valid[-1] - valid[-4]

    return {
        "water_raw": water_raw,
        "water_zscore_120": water_zscore_120,
        "water_slope_3": water_slope_3,
    }


# ═══════════════════════════════════════════════════════════════
# ATR（复用 stock-exchange/harness/stop_policy.py 的逻辑）
# ═══════════════════════════════════════════════════════════════

def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 20) -> np.ndarray:
    """True-range 滚动均值。"""
    h = np.asarray(high, float)
    l = np.asarray(low, float)
    c = np.asarray(close, float)
    n = len(c)
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    prev_c = c[:-1]
    tr[1:] = np.maximum(
        h[1:] - l[1:],
        np.maximum(np.abs(h[1:] - prev_c), np.abs(l[1:] - prev_c)),
    )
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        out[i] = tr[i - window + 1 : i + 1].mean()
    return out


# ═══════════════════════════════════════════════════════════════
# 涨跌停判断（复用 stock-exchange/analysis.py）
# ═══════════════════════════════════════════════════════════════

def board_limit_pct(code: str) -> float:
    """每日涨跌停幅度。"""
    if code.startswith(("688", "689", "300", "301")):
        return 20.0
    if code.startswith(("43", "83", "87", "88", "920")):
        return 30.0
    return 10.0


def is_limit_hit(
    code: str, price: float, prev_close: float, direction: str = "up"
) -> bool:
    """判断是否涨跌停。direction: 'up' | 'down'"""
    limit = board_limit_pct(code)
    if direction == "up":
        return price >= round(prev_close * (1 + limit / 100), 2)
    return price <= round(prev_close * (1 - limit / 100), 2)
