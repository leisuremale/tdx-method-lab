# 通达信三指标体系测试方案

日期：2026-07-04

## 1. 测试目标

要验证的不是“这套指标看起来准不准”，而是三个具体问题：

1. 副图动能体系能不能独立产生正期望。
2. 主图趋势确认是否能提高胜率、降低回撤或减少无效交易。
3. 水深作为退出辅助，是否能改善退出质量，而不是增加噪音。

最终判断标准：

```text
V1 副图基础版：证明核心动能规则是否有价值
V2 主图确认版：证明主图过滤是否优于 V1
V3 水深增强版：证明水深是否优于 V2
```

如果 V3 没有明显优于 V2，水深就不进入正式操作体系，只保留为人工参考。

## 2. 测试前准备工作

### 2.1 通达信/TdxQuant 环境

必须准备：

- 一套支持 TQ 策略功能的通达信终端。
- 能登录并下载日线/分钟线数据。
- 能找到终端目录下的 `PYPlugins/user/tqcenter.py`。
- 能运行官方 `tdxdata_test.py`。
- Python 环境能 import `tqcenter`。

验收命令或动作：

```text
1. 打开通达信终端并登录
2. 下载日线和分钟线盘后数据
3. 运行 tdxdata_test.py
4. 拉取 600519.SH 最近 5 根日线
5. 确认 Open/High/Low/Close/Volume/Amount 字段正常
```

当前风险：

- Mac App Store 版通达信大概率不具备完整 TdxQuant 环境。
- 完整测试可能需要 Windows 终端或 Windows 虚拟机。

### 2.2 MCP 接入准备

本库已准备 `tdxquant-mcp`：

- 目录：`vendor/tdxquant-mcp`
- Skill：`skills/tdxquant-mcp`

需要配置：

```text
TQ_PATH=/path/to/tdx/PYPlugins/user/tdxdata_test.py
MCP_HOST=127.0.0.1
MCP_PORT=8765
```

验收：

```text
uv sync --extra http
uv run python -m tdx_mcp.main_http
```

Agent 侧最小验证：

```text
tools_catalog
market_get_kline stock_list=["600519.SH"] period="1d" count=5 dividend_type="none"
utility_formula_run formula_name="KDJ" mode="zb"
```

### 2.3 公式资产整理

需要把三段源码保存成独立文件：

```text
formulas/main_chart.tdx
formulas/sub_chart.tdx
formulas/water_depth.tdx
```

并建立信号字典：

| 信号名 | 来源 | 公式条件 | 用途 |
|---|---|---|---|
| `trend_cross_up` | 主图 | `CROSS(CXHZB,GZZ)` | 入场候选 |
| `trend_cross_down` | 主图 | `CROSS(GZZ,CXHZB)` | 退出候选 |
| `strong_reversal` | 主图 | `TJ` | 入场候选 |
| `ema_multi_cross` | 主图 | `VAR11` | 入场候选 |
| `top_momentum_sell` | 主图 | `卖` | 退出候选 |
| `rsi_rollover_sell` | 主图 | `SWZB2` | 止盈观察 |
| `low_start` | 副图 | `天马` | 入场候选 |
| `momentum_hold` | 副图 | `观变>=REF(观变,1)` | 持仓 |
| `momentum_take_profit` | 副图 | `观变<=REF(观变,1)` | 止盈观察 |
| `macd_positive_shrink` | 副图 | `ZHZ>=0 AND ZHZ<REF(ZHZ,1)` | 止盈观察 |
| `macd_negative_break` | 副图 | `CROSS(0,ZHZ)` | 强退出 |
| `water_extreme` | 水深 | 自身滚动极端分位 | 退出辅助 |
| `water_turn` | 水深 | 水深方向拐点 | 退出辅助 |

### 2.4 数据样本准备

不要一开始全市场测试，先分三层样本。

#### 样本 A：手工验证样本

用途：核对公式转写是否与通达信图形一致。

建议 10-20 只：

- 强趋势股。
- 震荡股。
- 下跌股。
- 高价股。
- 低价股。
- 当前关注股，如深南电路、光迅科技、天孚通信等。

#### 样本 B：行业样本

用途：验证这套体系是否适用于 AI 产业链。

建议：

- CPO/光模块。
- PCB/覆铜板。
- 存储。
- 半导体设备。
- 连接器/铜连接。

每组 10-20 只。

#### 样本 C：扩展全市场样本

用途：检验稳健性。

过滤条件：

- 排除 ST。
- 排除上市不足 250 个交易日。
- 排除长期停牌/流动性太差。
- 可选：先排除北交所和科创板，等规则稳定后再加入。

### 2.5 回测框架准备

需要实现或准备：

- K 线数据加载。
- 公式信号计算。
- 信号事件表。
- 交易模拟器。
- 手续费/印花税/滑点。
- 结果报告。
- 交易明细导出。

最低字段：

```text
date
symbol
open
high
low
close
volume
amount
signal_name
signal_value
position
cash
equity
trade_action
trade_price
trade_reason
```

交易假设：

- 信号在收盘后确认，次日开盘或次日 VWAP 成交。
- 买入按 100 股整数。
- 加入交易成本。
- 涨跌停无法成交要单独处理。

## 3. 分阶段测试方案

### 阶段 0：公式一致性测试

目标：确认 Python/公式输出与通达信图形一致。

做法：

1. 选 10 只股票。
2. 在通达信中肉眼记录关键日期：`天马`、主图趋势上穿、主图卖点、副图止盈。
3. 用 TdxQuant/公式调用导出同一批信号。
4. 对比日期是否一致。

成功标准：

- 主要信号日期一致率 >= 95%。
- 不一致的地方必须能解释：未来函数、数据不足、复权口径、count 不足。

如果阶段 0 不通过，不进入回测。

### 阶段 1：V1 副图基础版

目标：验证副图自身是否有交易价值。

规则版本：

```text
买入候选：low_start = 天马
买入确认：观变上升 AND ZHZ改善
持仓：观变上升
止盈观察：观变下降 OR ZHZ正柱收缩
强退出：ZHZ跌破0
```

建议具体规则：

```text
买入：天马出现后 5 日内，观变连续 2 日上升
卖出：观变下降连续 2 日 OR ZHZ跌破0
```

对照组：

- 买入后固定持有 5/10/20 日。
- 普通 MACD 金叉买、死叉卖。
- 随机同日买入同股票池股票。

输出：

- 总收益、年化、最大回撤。
- 胜率、盈亏比、平均持有天数。
- 单笔最大亏损。
- 分年度表现。
- 分行业表现。

### 阶段 2：V2 主图确认版

目标：验证主图是否能提升副图规则。

规则：

```text
买入 = V1买入候选
      AND (trend_cross_up OR strong_reversal OR ema_multi_cross)

卖出 = V1卖出
      OR trend_cross_down
      OR top_momentum_sell
```

注意：

- 第一版不要使用 `趋顶/趋底` 作为硬条件，因为含 `XMA` 未来函数风险。
- 可以记录价格与 `趋顶/趋底` 的关系，但只做观察变量。

判断：

```text
如果 V2 胜率提高但收益下降：主图过滤可能过严。
如果 V2 回撤下降且收益不明显下降：主图有价值。
如果 V2 交易次数大幅减少但指标无改善：主图过滤无效。
```

### 阶段 3：V3 水深退出增强版

目标：验证水深作为退出辅助是否有增益。

不要使用水深原始值，先派生：

```text
water_rank_120 = 水深过去120日分位
water_slope_3 = 水深3日变化
water_zscore_120 = 水深120日标准化
water_turn = 水深方向变化
```

测试规则：

```text
买入 = V2买入
基础卖出 = V2卖出
水深增强卖出 = 副图止盈 AND (water_extreme OR water_turn)
最终卖出 = 基础卖出 OR 水深增强卖出
```

重点指标：

- 水深是否提前卖出后减少回撤。
- 水深是否导致过早卖出，错过主升浪。
- V3 相比 V2 的收益/回撤/错杀率是否改善。

水深保留条件：

```text
V3 最大回撤低于 V2
且年化收益不低于 V2 的 90%
且错杀率没有显著升高
```

### 阶段 4：稳健性测试

目标：排除过拟合。

测试切片：

- 牛市阶段。
- 熊市阶段。
- 震荡阶段。
- AI 行业样本。
- 非 AI 行业样本。
- 高价股/低价股。
- 高换手/低换手。

每个切片都要比较 V1/V2/V3。

### 阶段 5：盘中模拟监控

目标：验证是否能用于实盘提醒。

只做提醒，不下单。

流程：

1. 盘前生成候选清单。
2. 盘中定时刷新计划内股票。
3. 命中买入/止盈/退出条件时生成提醒。
4. 收盘后复盘提醒是否有效。

提醒内容：

```text
股票代码
股票名称
触发信号
当前价格
证据：主图/副图/水深
建议动作：观察/减仓/退出确认
风险：是否高位、是否缩量、是否接近趋顶
```

## 4. 评价指标

### 4.1 收益风险

- 总收益。
- 年化收益。
- 最大回撤。
- 夏普或收益回撤比。
- 单笔最大亏损。

### 4.2 交易质量

- 交易次数。
- 胜率。
- 盈亏比。
- 平均持有天数。
- 平均滑点敏感性。
- 换手率。

### 4.3 退出质量

这是测试水深的核心。

- 保护率：卖出后 N 日最大跌幅超过阈值的比例。
- 错杀率：卖出后 N 日最大涨幅超过阈值的比例。
- 提前性：卖出信号距离局部高点的天数。
- 回吐控制：从最高浮盈到实际卖出的回吐比例。

### 4.4 稳健性

- 分年度收益。
- 分行业收益。
- 分价格区间收益。
- 分市场环境收益。
- 参数扰动后是否仍有效。

## 5. 测试输出物

每轮测试应输出：

```text
reports/
  signal_consistency.md
  v1_subchart_baseline.md
  v2_main_confirm.md
  v3_water_exit.md
  robustness_by_regime.md
  trade_samples.csv
  signal_events.csv
```

每个报告必须包含：

- 样本范围。
- 数据时间范围。
- 规则定义。
- 参数。
- 结果表。
- 失败案例。
- 是否进入下一阶段的结论。

## 6. 当前最小下一步

在通达信终端还没装好前，可以先做：

1. 保存三段公式源码到 `formulas/`。
2. 把信号字典写成机器可读 YAML/JSON。
3. 先用普通 Python 复现副图 MACD/KDJ 逻辑。
4. 等 TdxQuant 可用后，用通达信公式输出校验 Python 复现结果。

装好 TdxQuant 后，第一条命令级目标：

```text
拉取 600519.SH 最近 300 根日线
计算副图 V1 信号
导出 signal_events.csv
人工对照通达信图上最近 10 个信号
```

