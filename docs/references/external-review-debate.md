# 外部审稿与方案辩论记录

日期：2026-07-04

目的：把主方案与独立子 Agent 的外部审稿结论合并，形成后续测试方案的改进清单。

## 1. 总体共识

这套通达信三指标体系不是成熟量化策略，而是一个“趋势过滤 + 动能确认 + 退出辅助”的半量化看盘系统。

更准确的定位：

```text
A 股短中线趋势动量系统
= 强趋势/阶段过滤
+ 副图低位或动能启动
+ 趋势持有
+ 动能衰减止盈
+ 水深辅助风险确认
```

因此，后续不应验证“某个图标准不准”，而应验证：

1. 副图动能信号是否有独立信息量。
2. 趋势/阶段过滤是否能减少假信号。
3. 主图复杂信号是否比简单趋势模板有增益。
4. 水深是否优于简单退出规则。
5. 加入 A 股交易约束后，结果是否仍可接受。

## 2. 独立审稿的关键挑战

### 2.1 主图不能整包使用

主图包含趋势线、均线、强势反包、涨停、通道、K 线染色、卖点等大量信号。最大风险是事后解释能力太强：

```text
上涨后总能找到一个买入解释
下跌后总能找到一个卖出解释
```

采纳：

- 主图拆成单独 feature 做事件研究。
- 不直接把整套主图作为 V2。
- 先增加简单趋势模板版本 V1.5，再比较复杂主图是否有额外价值。

### 2.2 XMA 默认进入禁用区

主图 `趋顶/趋底` 使用：

```tdx
XMA(XMA(H,25),25)
XMA(XMA(L,25),25)
```

`XMA` 存在未来函数/信号漂移争议。严谨测试中应按最高风险处理。

采纳：

- 第一轮回测完全剔除 `XMA` 通道。
- `趋顶/趋底` 只可作为人工看图参考，不参与机械买卖。
- 后续用 `EMA/MA/HHV/LLV/ATR Channel/Donchian Channel` 做替代对照。

### 2.3 水深必须和简单退出公平竞争

水深公式解释性弱、尺度不稳定，不能只和 V2 比。

采纳：

```text
V3 = V2.5 + 水深退出增强
V4a = V2.5 + N 日低点退出
V4b = V2.5 + ATR trailing stop
V4c = V2.5 + 最高浮盈回吐退出
```

如果 V3 不能稳定优于 V4，水深只保留为人工辅助指标。

### 2.4 先做事件研究，再做交易回测

如果单信号本身没有统计优势，直接组合成策略很容易变成调参幻觉。

采纳：

- 新增 V0 事件研究。
- 对每个信号统计后 1/3/5/10/20 日收益、最大上涨、最大回撤、胜率、中位收益。
- 按牛市/熊市/震荡市、AI/非 AI、高价/低价、高换手/低换手切片。

### 2.5 必须补组合和仓位层

当前体系主要回答“买不买、卖不卖”，还没有回答：

- 每只买多少。
- 最多持有几只。
- 同行业最大暴露多少。
- 单票最大亏损多少。
- 连续亏损后是否降仓。
- 市场整体弱势时是否停止开新仓。

采纳：

- 测试方案新增组合层与仓位层，不让单信号胜率替代系统可用性。

## 3. 采纳后的版本路线

```text
V0：事件研究，不交易
V0.5：固定持有基准
V1：副图动能基础版
V1.5：副图 + 简单趋势模板
V2：副图 + 主图拆分信号确认
V2.5：副图 + 趋势模板 + 多周期过滤
V3：V2.5 + 水深退出增强
V4：V2.5 + 简单趋势跟随退出
V5：组合与仓位规则
```

关键比较：

| 比较 | 回答的问题 |
|---|---|
| V1 vs V0.5 | 副图动能是否优于固定持有 |
| V1.5 vs V1 | 趋势过滤是否有效 |
| V2 vs V1.5 | 主图复杂信号是否有额外增益 |
| V2.5 vs V2 | 多周期过滤是否减少假信号 |
| V3 vs V2.5 | 水深是否改善退出 |
| V3 vs V4 | 水深是否优于简单退出 |
| V5 vs V2.5/V3/V4 | 组合和仓位是否改善实用性 |

## 4. 后续修改建议

优先级 P0：

- 在测试方案中加入 V0 事件研究。
- 标记 `XMA` 为禁用信号，不参与第一轮回测。
- 增加 A 股执行约束：T+1、涨跌停、停牌、ST、上市不足、复权、手续费、印花税、滑点、幸存者偏差。

优先级 P1：

- 增加 V1.5 简单趋势模板。
- 增加 V4 简单退出规则对照。
- 增加多周期过滤 V2.5。

优先级 P2：

- 增加组合和仓位规则 V5。
- 建立参数稳健性测试，避免只看最优参数点。

## 5. 外部参考

- Stan Weinstein Stage Analysis: https://traderlion.com/trading-strategies/stage-analysis/
- Mark Minervini Trend Template: https://www.chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/496-Mark-Minervini-Trend-Template-A-Step-by-Step-Guide-for-Beginners
- Elder Triple Screen: https://www.investopedia.com/articles/trading/03/040903.asp
- Turtle Trading: https://trendspider.com/learning-center/richard-dennis-turtle-trading-strategy/
- Time Series Momentum: https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- Backtrader Docs: https://www.backtrader.com/docu/
- vectorbt Docs: https://vectorbt.dev/
- QuantConnect LEAN Framework: https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview
- 通达信 XMA 讨论: https://www.vnpy.com/forum/topic/31307-jie-mi-tong-da-xin-han-shu-xma-ji-yu-shi-shi-de-wei-lai-han-shu
- BigQuant 回测指南: https://bigquant.com/wiki/doc/Z0tjAS5sWx
- A 股数据陷阱: https://quant67.com/post/quant/06-survivorship-bias/06-survivorship-bias.html
