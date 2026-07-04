# 外部量化/半量化体系参考

研究日期：2026-07-04

目标：为“通达信三指标体系”寻找可借鉴的外部方法论和工程实践。重点不是照搬，而是提炼可验证、可回测、可复盘的结构。

## 1. 结论摘要

我们的三指标体系最接近以下几类成熟思路的组合：

```text
Stan Weinstein 阶段分析：市场/个股处于哪个趋势阶段
Minervini Trend Template / VCP：只在强趋势和收缩蓄势里找机会
Elder Triple Screen：大周期定方向，中周期找回撤/动能，小周期执行
Turtle Trading：明确入场、退出、仓位和风险规则
Backtrader / vectorbt / LEAN：把指标视觉系统转成可测试工程体系
```

对我们的直接启发：

- 主图应承担“阶段/趋势过滤”角色，类似 Weinstein 和 Minervini。
- 副图应承担“动能确认/持仓管理”角色，类似 Elder 的 oscillator screen。
- 水深只适合作为“退出增强/风险确认”角色，类似 Turtle 的退出规则或 trailing stop 的补充，不应成为入场核心。
- 测试必须采用 V1/V2/V3 对照，而不是把整套视觉系统一次性回测。

## 2. 交易体系参考

### 2.1 Stan Weinstein Stage Analysis

核心思想：

- 股票走势分为四阶段：筑底、上涨、筑顶、下跌。
- 重点参与 Stage 2 上升阶段，回避 Stage 4 下跌阶段。
- 常用长周期均线、价格位置、成交量、相对强弱判断阶段。

可借鉴点：

- 给我们的主图增加“阶段标签”，不要只看当天颜色。
- `CXHZB>=GZZ`、`MA3/MA13/MA34`、`牧马/操盘` 可以合成一个趋势阶段分数。
- 回测时先过滤掉明显 Stage 4 股票，减少副图低位金叉的假信号。

映射到三指标体系：

| Weinstein | 我们的对应 |
|---|---|
| Stage 1 筑底 | 副图 `天马` 可作为低位启动候选，但需要主图确认 |
| Stage 2 上涨 | 主图趋势转强 + 副图持股 |
| Stage 3 筑顶 | 主图 `趋顶` 附近 + 副图止盈 + 水深风险 |
| Stage 4 下跌 | 主图趋势转弱 + ZHZ 负动能恶化 |

注意：

- Weinstein 偏中长周期，不能直接拿来做短线图标交易。
- 我们可以借它的“阶段过滤”，不是照搬周期参数。

参考：

- Investopedia: Trading With Stage Analysis
- TraderLion: The Complete Guide to Stan Weinstein's Stage Analysis

### 2.2 Mark Minervini Trend Template / VCP

核心思想：

- 先筛出强趋势股票：价格在关键均线上方，均线多头排列，相对强度强。
- 再等 VCP，即波动逐步收缩、成交量收缩、突破时放量。
- 强调只做市场领导股，不在弱股里找便宜。

可借鉴点：

- 主图不应该只是买卖提示，而应先做“是否有资格交易”的趋势模板。
- `TJ` 强势反包、涨停高亮、`VAR11` 多空金叉，可以作为突破/强势行为。
- 副图 `天马` 如果发生在弱趋势里，应该降低权重；如果发生在趋势模板合格股票里，价值更高。

可加入的过滤：

```text
price_above_ma = C > MA(C,50) AND C > MA(C,150) AND C > MA(C,200)
ma_uptrend = MA(C,50) > MA(C,150) AND MA(C,150) > MA(C,200)
relative_strength = 个股近 N 日收益 > 指数近 N 日收益
volume_contract = 回调期间成交量收缩
```

对我们方案的优化：

- 在 V2 主图确认版中增加“趋势模板合格”子版本。
- 把 `TJ` 和涨停识别作为强势突破事件，不直接当买点。
- 对高位连续加速后出现副图止盈/水深风险的股票，优先止盈。

参考：

- Deepvue: Mark Minervini Trend Template
- TrendSpider: Minervini Trend Template / VCP
- ChartMill: Minervini Trend Template guide

### 2.3 Alexander Elder Triple Screen

核心思想：

- 用多重过滤解决单指标矛盾。
- 大周期定趋势，中周期找动能/回撤，小周期执行。
- 趋势指标和震荡指标搭配使用。

这和我们的三指标体系很像：

| Elder 三重滤网 | 我们的对应 |
|---|---|
| 第一屏：大方向 | 主图趋势/阶段 |
| 第二屏：动能或回撤 | 副图 `天马`、ZHZ、观变 |
| 第三屏：执行 | 具体 K 线突破、次日开盘/盘中提醒 |

可借鉴点：

- 不允许副图单独买入，必须服从主图方向。
- 不允许主图强势但副图动能恶化时追买。
- 可以引入多周期：周线主图定阶段，日线副图找信号，30/60 分钟只做执行提醒。

对我们方案的优化：

```text
周线过滤：只做周线趋势不差的股票
日线信号：副图天马/观变/ZHZ
盘中执行：突破昨日高点、回踩不破、成交量确认
```

参考：

- Investopedia: Triple Screen Trading System
- QuantifiedStrategies: Alexander Elder Triple Screen Strategy

### 2.4 Turtle Trading / Trend Following

核心思想：

- 完整系统必须包含：市场选择、入场、退出、仓位、风险控制。
- 入场和退出都要机械化。
- 用波动率做仓位和止损。

可借鉴点：

- 我们不能只研究指标，还必须定义仓位。
- 水深如果要存在，应证明它改善“退出质量”；否则用更简单的 N 日低点/ATR/回吐保护。
- 每个交易都要有同一套风险单位，而不是看图决定仓位。

可测试替代退出：

```text
exit_n_day_low = C < LLV(L, 10 or 20)
atr_stop = C < entry_price - k * ATR
profit_giveback = peak_gain >= X% AND current_gain <= peak_gain * 0.5
indicator_exit = 副图止盈 + 主图卖点
water_exit = indicator_exit + 水深确认
```

对我们方案的优化：

- V3 不只和 V2 比，还要和简单 Turtle 式退出比。
- 如果水深不如简单 N 日低点/ATR/回吐保护，就不要复杂化。

参考：

- TrendSpider: Richard Dennis' Turtle Trading Strategy
- Macro Ops: Turtle Trading Rules and Strategy
- QuantifiedStrategies: Turtle Trading Strategy

## 3. 工程体系参考

### 3.1 Backtrader

适合：

- 事件驱动回测。
- 单策略从信号到交易明细、订单、手续费、滑点的模拟。
- 多数据、多周期、指标、分析器。

对我们有用：

- 用 Backtrader 的结构来组织策略：Data Feed -> Indicator -> Strategy -> Broker -> Analyzer。
- 适合做“V1/V2/V3 回测报告”。
- 对交易成本、订单成交、滑点更容易建模。

不足：

- 参数大规模网格搜索不如 vectorbt 快。
- 如果只想快速扫很多参数，可能偏重。

参考：

- Backtrader official docs
- Backtrader package docs

### 3.2 vectorbt

适合：

- 大量参数组合。
- 信号矩阵化。
- 快速比较 V1/V2/V3、水深分位阈值、观变连续天数等。

对我们有用：

- 第一轮用 vectorbt 做大规模信号验证和参数敏感性。
- 用它验证“水深不同分位阈值是否稳定”。
- 用它快速跑行业切片、年份切片。

不足：

- 对真实订单细节、涨跌停、成交量约束，需要额外处理。
- A 股交易规则要自己补。

参考：

- vectorbt official docs
- vectorbt PyPI / GitHub

### 3.3 QuantConnect LEAN

适合：

- 研究、回测、优化、实盘的一体化引擎。
- 事件驱动、模块化、专业工程架构。

对我们有用：

- 作为长期架构参考：同一份算法尽量能从研究到回测再到模拟/实盘。
- 可以借鉴它的模块边界：Universe、Alpha、Portfolio、Risk、Execution。

不足：

- 对 A 股和通达信公式体系不是原生最适合。
- 当前阶段不需要引入这么重的引擎。

参考：

- LEAN official site
- QuantConnect docs

## 4. 如何改进我们的三指标测试方案

### 4.1 增加“趋势模板过滤”

在 V2 主图确认版之前，先加一个 V1.5：

```text
V1 = 副图基础版
V1.5 = 副图基础版 + 趋势模板
V2 = 副图基础版 + 主图信号确认
V3 = V2 + 水深退出增强
```

趋势模板可参考 Minervini/Weinstein：

```text
C > MA50
MA50 > MA150
MA150 > MA200
MA50 上行
个股近 60/120 日相对指数更强
```

### 4.2 增加多周期过滤

参考 Elder：

```text
周线：阶段/趋势过滤
日线：副图信号
分钟线：只做执行提醒，不改变日线规则
```

这样可以减少副图低位金叉在下跌趋势中的假启动。

### 4.3 水深必须和简单退出规则对照

参考 Turtle：

```text
退出 A：副图止盈
退出 B：副图止盈 + 主图卖点
退出 C：副图止盈 + 水深确认
退出 D：N 日低点退出
退出 E：ATR / 回吐保护退出
```

只有 C 明显优于 B/D/E，水深才有保留价值。

### 4.4 把主图视觉系统拆成 feature，不要整体回测

主图里信号太多，应拆成字段：

```text
trend_cross_up
trend_cross_down
strong_reversal
ema_multi_cross
top_momentum_sell
rsi_rollover_sell
near_trend_top
near_trend_bottom
```

每个字段单独统计：

- 信号后 5/10/20 日收益。
- 信号发生时市场环境。
- 和副图信号叠加后的增益。

### 4.5 先用 vectorbt 快速扫，再用 Backtrader 精细复核

推荐工程路线：

```text
第一轮：pandas/vectorbt 快速生成信号矩阵和参数敏感性
第二轮：Backtrader 或自研事件回测模拟 A 股成交、手续费、涨跌停
第三轮：TdxQuant 回传信号到通达信界面人工抽样复盘
```

## 5. 建议新增测试版本

```text
V0: 买入后固定持有 N 日基准
V1: 副图动能基础版
V1.5: V1 + 趋势模板过滤
V2: V1 + 主图确认
V2.5: V2 + 多周期过滤
V3: V2.5 + 水深退出增强
V4: V2.5 + 简单趋势跟随退出（N日低点/ATR/回吐保护）
```

关键比较：

- V1.5 是否优于 V1：趋势模板有没有价值。
- V2 是否优于 V1.5：主图信号确认有没有增益。
- V2.5 是否优于 V2：多周期是否减少假信号。
- V3 是否优于 V2.5：水深有没有价值。
- V3 是否优于 V4：水深是否优于更简单的退出规则。

## 6. 参考链接

- Stan Weinstein / Stage Analysis:
  - https://www.investopedia.com/articles/investing/070715/trading-stage-analysis.asp
  - https://traderlion.com/trading-strategies/stage-analysis/
- Minervini / Trend Template / VCP:
  - https://deepvue.com/screener/minervini-trend-template/
  - https://trendspider.com/trading-tools-store/collection/minervini-trend-template-vcp/
  - https://www.chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/496-Mark-Minervini-Trend-Template-A-Step-by-Step-Guide-for-Beginners
- Elder Triple Screen:
  - https://www.investopedia.com/articles/trading/03/040903.asp
  - https://www.quantifiedstrategies.com/alexander-elder-triple-screen-strategy/
- Turtle Trading:
  - https://trendspider.com/learning-center/richard-dennis-turtle-trading-strategy/
  - https://macro-ops.com/richard-dennis-turtle-trading-strategy-explained/
  - https://www.quantifiedstrategies.com/turtle-trading-strategy/
- Backtesting / Engineering:
  - https://www.backtrader.com/docu/
  - https://vectorbt.dev/
  - https://www.lean.io/
  - https://kernc.github.io/backtesting.py/doc/backtesting/

