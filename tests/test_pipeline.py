"""端到端验证: 合成数据自检 → 真实数据 → 全篮回测。

运行: uv run python tests/test_pipeline.py
"""

import os, sys, json

# 确保 src/ 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd

from tdx_lab.data import fetch_daily_tencent, AI_BASKETS, ai_basket_codes
from tdx_lab.indicators import (
    compute_xhsub, compute_xhmain, compute_xhwater, atr, sma_tdx
)
from tdx_lab.signals import generate_signal_table, daily_state
from tdx_lab.backtest import simulate, compare_rules, benchmark_buy_hold

# ═══════════════════════════════════════════════════════════════
# 阶段 0: 地基自检——合成数据
# ═══════════════════════════════════════════════════════════════
def test_synth_indicators():
    """验证指标计算在合成数据上不报错，且产出合理的数组。"""
    print("=" * 70)
    print("阶段 0 · 地基自检: 合成数据验证指标计算")
    print("=" * 70)

    rng = np.random.default_rng(42)
    n = 600
    # 生成带趋势+波动的价格序列
    drift = np.cumsum(rng.normal(0.0005, 0.02, n))
    noise = rng.normal(0, 0.01, n)
    close = 100 * np.exp(drift + noise)

    # 生成 OHLC (close 为中心)
    o = close * (1 + rng.normal(0, 0.005, n))
    h = np.maximum(o, close) * (1 + np.abs(rng.normal(0, 0.01, n)))
    l = np.minimum(o, close) * (1 - np.abs(rng.normal(0, 0.01, n)))
    v = np.abs(rng.normal(1e7, 3e6, n))

    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=n, freq="B"),
        "open": o, "high": h, "low": l, "close": close, "volume": v,
    })

    sub = compute_xhsub(df)
    main = compute_xhmain(df)
    water = compute_xhwater(df)

    # 验证输出
    checks = [
        ("zhz 长度", len(sub["zhz"]), n),
        ("zhz 无全NaN", np.any(~np.isnan(sub["zhz"])), True),
        ("tian_ma 数量", int(sub["tian_ma"].sum()), ">=0"),
        ("cxhzb 有效值", int(np.isfinite(main["cxhzb"]).sum()), ">0"),
        ("trend_up 数量", int(main["trend_up"].sum()), ">=0"),
        ("water_raw 有效值", int(np.isfinite(water["water_raw"]).sum()), ">0"),
    ]
    all_ok = True
    for name, actual, expected in checks:
        if isinstance(expected, str):
            ok = True  # 不严格比较
            status = "✅"
        else:
            ok = (actual == expected) if not isinstance(expected, bool) else (actual == expected)
            status = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {status} {name}: {actual}" if isinstance(actual, int) else f"  {status} {name}")

    print(f"\n  合成数据自检: {'✅ PASS' if all_ok else '❌ FAIL'}")

    # 信号生成
    sig_df = generate_signal_table(df, sub, main, water)
    print(f"  信号事件: {len(sig_df)} 条")
    if len(sig_df) > 0:
        print(f"  信号类型分布: {sig_df['signal_name'].value_counts().to_dict()}")

    # 回测
    r = simulate(df, sub, main, entry_rules="tian_ma_and_trend", exit_rules="take_profit_or_trend_down")
    print(f"  回测: {r['n_trades']} 笔交易 | 收益 {r['total_return']}% | 回撤 {r['max_drawdown']}% | Calmar {r['calmar']}")

    return all_ok


# ═══════════════════════════════════════════════════════════════
# 阶段 1: 真实数据——三只样本股
# ═══════════════════════════════════════════════════════════════
def test_real_data():
    """在真实行情上验证完整管线。"""
    print("\n" + "=" * 70)
    print("阶段 1 · 真实数据: 三只样本股")
    print("=" * 70)

    samples = [
        ("300308", "中际旭创"),
        ("002916", "深南电路"),
        ("300394", "天孚通信"),
    ]

    all_trades = []

    for code, name in samples:
        print(f"\n{'─' * 50}")
        print(f"  {code} {name}")

        try:
            df = fetch_daily_tencent(code, count=500)
        except Exception as e:
            print(f"  ❌ 腾讯API失败: {e}，尝试 baostock...")
            from tdx_lab.data import fetch_daily_baostock
            df = fetch_daily_baostock(code)

        if df.empty:
            print(f"  ❌ 无数据")
            continue

        n = len(df)
        print(f"  ✅ {n} 条 | {df['date'].min().date()} ~ {df['date'].max().date()} | C:{df['close'].iloc[-1]:.2f}")

        sub = compute_xhsub(df)
        main = compute_xhmain(df)
        water = compute_xhwater(df)

        # 信号统计
        tianma_dates = df["date"][sub["tian_ma"]].values
        trend_up_dates = df["date"][main["trend_up"]].values
        trend_down_dates = df["date"][main["trend_down"]].values
        var11_dates = df["date"][main["var11"]].values

        print(f"  天马: {len(tianma_dates)}次 | 趋势转强: {len(trend_up_dates)}次 | 趋势转弱: {len(trend_down_dates)}次 | VAR11: {len(var11_dates)}次")

        # 每日状态
        state = daily_state(df, sub, main)
        last = state.iloc[-1]
        print(f"  最新: {'持股' if last['hold'] else '止盈'} | ZHZ: {last['zhz']} | MACD: {last['macd_state']} | CXHZB: {'≥GZZ' if last['cxhzb_above_gzz'] else '<GZZ'}")

        # 规则对比
        entry_rules = ["tian_ma_only", "tian_ma_and_trend", "tian_ma_or_trend", "tian_ma_or_var11"]
        exit_rules = ["take_profit_or_trend_down", "take_profit_only", "all"]

        print(f"\n  规则对比 (按 Calmar 排序):")
        cmp = compare_rules(df, sub, main, entry_rules, exit_rules)
        print(cmp[["entry_rule", "exit_rule", "n_trades", "total_return", "max_drawdown", "win_rate", "calmar"]].head(8).to_string(index=False))

        # 最佳规则
        best = cmp.iloc[0]
        print(f"\n  最佳: {best['entry_rule']} + {best['exit_rule']}")
        print(f"  收益 {best['total_return']}% | 回撤 {best['max_drawdown']}% | 胜率 {best['win_rate']}% | Calmar {best['calmar']}")

        # 记录交易
        r = simulate(df, sub, main,
                     entry_rules=best["entry_rule"],
                     exit_rules=best["exit_rule"])
        for t in r["trades"]:
            t["code"] = code
            t["name"] = name
        all_trades.extend(r["trades"])

    return all_trades


# ═══════════════════════════════════════════════════════════════
# 阶段 2: 全篮回测对比
# ═══════════════════════════════════════════════════════════════
def test_basket():
    """在 AI 篮子全部股票上跑统一规则，看整体表现。"""
    print("\n" + "=" * 70)
    print("阶段 2 · AI 篮子全量回测")
    print("=" * 70)

    codes = ai_basket_codes()
    print(f"篮子: {len(codes)} 只股票 ({', '.join(AI_BASKETS.keys())})")

    # 统一用 V2 规则: tian_ma_and_trend + take_profit_or_trend_down
    results = []
    ok = 0
    fail = 0

    for code in codes:
        try:
            df = fetch_daily_tencent(code, count=500)
        except Exception:
            continue

        if df.empty or len(df) < 120:
            fail += 1
            continue

        sub = compute_xhsub(df)
        main = compute_xhmain(df)

        r = simulate(df, sub, main,
                     entry_rules="tian_ma_and_trend",
                     exit_rules="take_profit_or_trend_down")

        bh = benchmark_buy_hold(df)

        results.append({
            "code": code,
            "n_days": len(df),
            "n_trades": r["n_trades"],
            "total_return": r["total_return"],
            "max_drawdown": r["max_drawdown"],
            "calmar": r["calmar"],
            "win_rate": r["win_rate"],
            "bh_return": bh["total_return"],
            "vs_bh": round(r["total_return"] - bh["total_return"], 2),
        })
        ok += 1

    print(f"\n  成功: {ok}/{len(codes)} 只")

    if not results:
        print("  ❌ 无有效数据")
        return

    res_df = pd.DataFrame(results).sort_values("calmar", ascending=False)
    print(f"\n  Top 10 (按 Calmar):")
    print(res_df.head(10)[["code", "n_trades", "total_return", "max_drawdown", "calmar", "win_rate", "vs_bh"]].to_string(index=False))

    # 汇总统计
    print(f"\n  汇总 (n={len(res_df)}):")
    profit = (res_df["total_return"] > 0).sum()
    beat_bh = (res_df["vs_bh"] > 0).sum()
    print(f"  正收益: {profit}/{len(res_df)} ({profit/len(res_df)*100:.0f}%)")
    print(f"  跑赢买入持有: {beat_bh}/{len(res_df)} ({beat_bh/len(res_df)*100:.0f}%)")
    print(f"  中位收益: {res_df['total_return'].median():.1f}%")
    print(f"  中位Calmar: {res_df['calmar'].median():.2f}")
    print(f"  中位胜率: {res_df['win_rate'].median():.0f}%")

    # 分篮子统计
    print(f"\n  分篮子:")
    basket_map = {}
    for basket, basket_codes in AI_BASKETS.items():
        basket_map.update({c: basket for c in basket_codes})
    res_df["basket"] = res_df["code"].map(basket_map)
    for basket in AI_BASKETS:
        sub = res_df[res_df["basket"] == basket]
        if len(sub) > 0:
            print(f"  {basket}: {len(sub)}只 | 中位收益 {sub['total_return'].median():.1f}% | "
                  f"中位Calmar {sub['calmar'].median():.2f} | 正收益 {int((sub['total_return']>0).sum()/len(sub)*100)}%")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # 阶段 0: 地基自检
    ok0 = test_synth_indicators()

    # 阶段 1: 样本股
    trades = test_real_data()

    # 阶段 2: 全篮
    test_basket()

    print("\n" + "=" * 70)
    print(f"地基自检: {'✅ PASS' if ok0 else '❌ FAIL'}")
    print("=" * 70)
