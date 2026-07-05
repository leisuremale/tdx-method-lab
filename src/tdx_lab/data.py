"""行情数据获取——腾讯证券 API（前复权日线）。

复用 stock-exchange/market_io.py 已验证的接口模式。
东方财富接口本机被墙，走腾讯；baostock 备用做批量拉取。
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}


def tx_symbol(code: str) -> str:
    """腾讯代码格式：sh600519 / sz000001。复用 stock-exchange/analysis.py 逻辑。"""
    return ("sh" if code.startswith(("6", "9")) else "sz") + code


def fetch_daily_tencent(code: str, count: int = 500) -> pd.DataFrame:
    """从腾讯API获取前复权日线（最多约500条）。

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
        date 列为 datetime64，其他为 float64，按日期升序。
    """
    symbol = tx_symbol(code)
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={symbol},day,,,{count},qfq"
    )
    resp = requests.get(url, timeout=30, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    stock_data = data.get("data", {})
    if not isinstance(stock_data, dict):
        return pd.DataFrame()

    raw = stock_data.get(symbol, {}).get("qfqday", [])
    if not raw:
        return pd.DataFrame()

    # 腾讯格式: [date, open, close, high, low, volume]
    rows = [
        {
            "date": item[0],
            "open": float(item[1]),
            "close": float(item[2]),
            "high": float(item[3]),
            "low": float(item[4]),
            "volume": float(item[5]),
        }
        for item in raw
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def fetch_daily_baostock(
    code: str, start: str = "2021-01-01", end: str = "2026-07-01"
) -> pd.DataFrame:
    """从 baostock 获取前复权日线（适合批量、长周期）。

    Args:
        code: 纯数字代码如 "300308"
        start/end: "YYYY-MM-DD"

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    import baostock as bs

    bao = ("sh." if code.startswith(("6", "9")) else "sz.") + code
    bs.login()
    try:
        rs = bs.query_history_k_data_plus(
            bao,
            "date,open,high,low,close,volume",
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag="2",  # 前复权
        )
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        if len(rows) <= 60:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        return df
    finally:
        bs.logout()


def fetch_batch_baostock(
    codes: list[str],
    start: str = "2021-01-01",
    end: str = "2026-07-01",
    sleep: float = 0.05,
) -> dict[str, pd.DataFrame]:
    """批量拉取多只股票的 baostock 日线（串行，baostock 并发会截断）。

    Returns:
        {code: DataFrame}，缺失数据的股票不在字典中。
    """
    import baostock as bs

    bs.login()
    results = {}
    try:
        for i, code in enumerate(codes, 1):
            bao = ("sh." if code.startswith(("6", "9")) else "sz.") + code
            try:
                rs = bs.query_history_k_data_plus(
                    bao,
                    "date,open,high,low,close,volume",
                    start_date=start,
                    end_date=end,
                    frequency="d",
                    adjustflag="2",
                )
                rows = []
                while rs.error_code == "0" and rs.next():
                    rows.append(rs.get_row_data())
                if len(rows) > 60:
                    df = pd.DataFrame(
                        rows, columns=["date", "open", "high", "low", "close", "volume"]
                    )
                    for col in ["open", "high", "low", "close", "volume"]:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.dropna(subset=["close"]).reset_index(drop=True)
                    results[code] = df
            except Exception:
                pass
            if i % 20 == 0:
                print(f"  [{i}/{len(codes)}] ok={len(results)} ...")
            time.sleep(sleep)
    finally:
        bs.logout()
    return results


# ── AI 产业链篮子（复用 stock-exchange/harness/fetch_ohlc_cache.py）──
AI_BASKETS: dict[str, list[str]] = {
    "AI-CPO": ["300308", "300502", "300394", "002281", "300570", "603083", "000988", "300548", "301205", "300620"],
    "AI-PCB": ["002463", "600183", "300476", "002916", "002938", "002384", "002436", "603228", "603920", "001389"],
    "AI-半导体": ["002371", "603501", "300661", "002049", "300782", "600584", "002156", "600703", "600460"],
    "AI-存储": ["603986", "301308", "300223", "001309", "300475", "300042", "300302", "000021", "300672", "300857"],
    "AI-其它": ["601138", "000977", "603019", "002230", "601360", "300418", "300229", "000034", "002415", "000938"],
}


def ai_basket_codes() -> list[str]:
    """AI 篮子全部股票代码（去重）。"""
    seen = set()
    codes = []
    for lst in AI_BASKETS.values():
        for c in lst:
            if c not in seen:
                codes.append(c)
                seen.add(c)
    return codes
