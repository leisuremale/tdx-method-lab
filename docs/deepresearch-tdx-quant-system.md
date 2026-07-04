# Deep Research: 用通达信工具搭建量化交易体系

研究日期：2026-07-04

## 一句话结论

通达信工具链适合搭一套“本地终端数据 + Python 策略研究 + 公式/预警联动 + MCP 给 Agent 调用”的个人量化体系。正确路径不是先做自动下单，而是：

1. 先用 TdxQuant 打通数据、公式和回测。
2. 再把策略信号回传到通达信界面做可视化和预警。
3. 再通过 MCP 让 Agent 调行情、财务、板块、公式和候选结果。
4. 最后才评估模拟交易和实盘交易，且实盘默认保留人工确认。

原因：官方文档明确 TdxQuant 基于通达信金融终端，通过 Python API 获取行情和执行交易；同时也要求运行前预先启动支持 TQ 策略功能的终端。交易函数支持下单，但实盘账户会提示用户确认；实盘自动下单还需要券商开通支持 TQ 的版本。

## 1. 可用工具版图

### 1.1 官方底座：TdxQuant

TdxQuant 是通达信官方的 Python 量化策略运行框架，依赖通达信金融终端、专业研究版、量化模拟版或期货通等终端。官方描述的核心能力包括：

- 行情数据：实时/历史快照、K 线、分笔。
- 基本面数据：除权除息、基本财务、专业财务、股票交易数据、市场数据。
- 标的资料：股票、基金、指数、板块、期货、宏观、可转债、期权。
- 策略研发、历史回测、实时监控、信号预警、模拟交易、实盘执行。

关键前提：

- 需要安装并登录通达信终端。
- 需要在终端里下载日线、分钟线等盘后数据。
- 需要从终端目录的 `PYPlugins/user` 运行或引用 `tqcenter.py`。
- 所有策略连接终端前都要 `tq.initialize(__file__)`。

### 1.2 官方界面联动能力

TdxQuant 不只是“取数据”。它还能把策略结果送回通达信界面：

- `send_warn`：发送预警信号到 TQ 策略界面。
- `send_bt_data`：发送回测数据到 TQ，可配合通达信公式 `SIGNALS_TQ` 在 K 线上展示自定义序列。
- `send_user_block`：写入自选/自定义板块。
- `exec_to_tdx`：打开客户端里的个股页面或功能页面。

这意味着个人体系可以保留通达信界面的看盘体验，同时把策略计算放到 Python。

### 1.3 Agent 接入层：tdxquant-mcp

本次找到的最合适 Agent 连接器是 `lingfan/tdxquant-mcp`。它把本地 `tqcenter.py` 封装成 MCP，支持 stdio 和 HTTP/SSE。已复制到本测试库：

- 候选仓库：`vendor/tdxquant-mcp`
- Skill：`skills/tdxquant-mcp`

MCP 工具覆盖：

- `market_get_kline`、`market_get_snapshot`：行情和快照。
- `stock_get_info`、`stock_get_more_info`、`stock_get_capital_info`：股票资料。
- `sector_list`、`sector_stocks`、`sector_get_relation`：板块。
- `financial_get_report_range`、`financial_get_report_by_date`：财务。
- `utility_formula_run` / `formula_run`：执行通达信公式。
- `trade_query_asset`、`trade_query_orders`、`trade_query_positions`：账户查询。
- `trade_order_stock`、`trade_cancel_order_stock`：交易操作，默认 dry-run。
- `tools_catalog`：工具目录，应作为 Agent 首次调用入口。

## 2. 推荐体系架构

```text
通达信终端
  ├─ 行情/财务/板块/公式/账户
  ├─ 盘后数据下载与本地缓存
  └─ TQ 策略界面/预警/自定义板块
        ↑
        │ tqcenter.py
        ↓
Python 策略层
  ├─ 数据获取 adapter
  ├─ 公式调用 adapter
  ├─ 策略信号 engine
  ├─ 回测 harness
  ├─ 模拟/实盘执行 adapter
  └─ 日志/复盘/风控审计
        ↑
        │ MCP: tdxquant-mcp
        ↓
Agent 层
  ├─ 查询行情/财务/板块
  ├─ 调用公式和解释结果
  ├─ 生成候选清单
  ├─ 复盘交易纪律
  └─ 发飞书提醒，但不默认真实下单
```

核心分工：

- 通达信终端负责权威数据源、公式系统、界面展示、交易通道。
- Python 负责可测试策略逻辑和回测。
- MCP 负责让 Agent 能稳定读数据、跑公式、查账户、生成报告。
- 飞书只做通知和确认，不做交易执行源。

## 3. 分层设计

### 3.1 数据层

目标：建立可复现的数据入口，避免每个策略直接散写 `tq.get_market_data`。

最小能力：

- 获取单股/多股日线、分钟线：`get_market_data` / MCP `market_get_kline`
- 获取快照：`get_market_snapshot` / MCP `market_get_snapshot`
- 获取股票基础资料和扩展资料。
- 获取板块列表、板块成分、股票所属板块。
- 获取财务报告和交易衍生数据。
- 获取交易日历。

注意点：

- 官方示例说明 K 线数据需要先在客户端中下载对应盘后数据。
- `refresh_kline` 目前官方示例提示只支持部分周期，且不建议一次更新太多，避免阻塞策略和客户端。
- 前复权数据对齐要谨慎。官方 FAQ 提到某些日期前复权数据要取完整数据后再和客户端显示对比。

建议落地：

- 建 `src/tdx_lab/data.py`，封装 `load_bars(symbols, period, start, end, adjust)`。
- 数据返回统一成 long format：`date, symbol, open, high, low, close, volume, amount, adj_factor`。
- 每次研究保存原始响应摘要和数据版本，便于复盘。

### 3.2 公式层

目标：把“通达信公式”纳入可验证流程，而不是只在客户端里肉眼看。

通达信 TdxQuant 已支持：

- 调用技术指标公式 `formula_zb`。
- 调用条件选股公式 `formula_xg`。
- 调用专家系统公式 `formula_exp`。
- 批量调用公式。
- 获取公式列表和公式信息。

MCP 对应入口：

- `utility_formula_run`
- `formula_run`

建议落地：

- 将交易方法中的通达信公式保留原文，放入 `formulas/`。
- 每个公式配一个 Python 验证用例，验证输入 K 线数量、输出字段、空值位置。
- 对选股公式，统一输出：`symbol, date, signal, raw_values, formula_name, formula_version`。

关键坑：

- 公式需要足够 K 线数量。官方 FAQ 提到，如果 `count` 覆盖不到公式最大参数，前面结果会为空。
- 客户端条件选股可能使用全量本地数据；批量公式调用如果 `count` 不合理，结果会少。

### 3.3 策略研究层

目标：把交易方法拆成明确的、可反证的规则。

每个方法至少定义：

- universe：股票池，例如全 A、指定板块、AI 产业链、通达信概念板块。
- entry：买入条件，来自公式、价格结构、量价、板块联动或财务过滤。
- exit：卖出条件。
- sizing：仓位和加减仓。
- risk：单票、组合、回撤、流动性、停牌/ST/涨跌停限制。
- timing：日线、分钟线、盘中还是盘后。
- cost：佣金、印花税、滑点、无法成交处理。

建议先不要接实盘交易。先做三类研究：

1. 单股票历史回放：验证公式信号是否符合肉眼认知。
2. 横截面选股回测：验证同日多个候选的收益分布。
3. 组合回测：验证仓位和风控规则。

### 3.4 回测层

目标：回测要独立于通达信界面，但可以把结果回传通达信展示。

官方示例中有 `send_bt_data`，可把回测数据送到 TQ，再用 `SIGNALS_TQ(ID, TYPE)` 在公式管理器中引用。这很适合做“策略结果在 K 线上复盘”。

建议回测输出：

- 交易明细：买卖日期、价格、数量、手续费、原因。
- 每日资产：现金、持仓市值、总权益、回撤。
- 信号明细：触发字段、公式输出、过滤器结果。
- 对照组：买入持有、指数、随机入场、同板块等权。
- 质量指标：胜率、盈亏比、最大回撤、年化、换手、滑点敏感性。

合格标准：

- 必须有样本外区间。
- 必须有交易成本。
- 必须有失败案例复盘。
- 必须有随机/朴素基准，不只看绝对收益。

### 3.5 盘中监控层

目标：把盘中动作限制在“提醒和确认”，避免 Agent 盘中乱交易。

通达信能力：

- 快照/订阅行情。
- `send_warn` 推送预警到 TQ 策略界面。
- MCP 可由 Agent 查快照、K 线、公式结果。

建议流程：

1. 盘前生成今日监控清单。
2. 盘中只监控已有计划内股票。
3. 命中条件后发飞书提醒：股票、名称、触发规则、价格、证据、建议动作。
4. Le 手动确认是否操作。
5. 收盘后自动复盘：命中但未操作、操作但未命中、滑点、次日表现。

### 3.6 执行层

官方 `order_stock` 支持买卖下单，参数包括账户句柄、证券代码、委托类型、数量、报价类型、价格、是否手动确认。返回值中 `Value=1` 表示待用户确认，`Value=2` 表示成功。

但这里要保守：

- 实盘交易账户会提示下单让用户确认。
- 自动下单需要开户券商开通并使用对应支持 TQ 的版本。
- MCP 中 `trade_order_stock` 和 `trade_cancel_order_stock` 默认 dry-run，不能默认关闭。

建议执行成熟度分四级：

| 级别 | 说明 | 是否允许 |
|---|---|---|
| L0 | 只研究数据和公式 | 现在就做 |
| L1 | 只发预警，不查账户 | 装好终端后做 |
| L2 | 查询账户/持仓/委托，只读 | 终端和权限确认后做 |
| L3 | 下单 dry-run，生成预览 | 明确授权后做 |
| L4 | 实盘下单，人工确认 | 最后再评估 |
| L5 | 无人值守自动下单 | 当前不建议 |

## 4. 最小可行体系

第一阶段目标不是“全自动交易”，而是搭一个能验证方法真假的闭环。

### 阶段 A：安装与连接

成功标准：

- 通达信/TdxQuant 终端可打开并登录。
- `PYPlugins/user/tqcenter.py` 存在。
- 能运行官方 `tdxdata_test.py`。
- 能获取 `000001.SZ` 或 `600519.SH` 的 5 根日线。

### 阶段 B：MCP 联通

成功标准：

- `tdxquant-mcp` 可启动。
- Agent 能调用 `tools_catalog`。
- Agent 能调用 `market_get_kline` 获取 5 根日线。
- Agent 能调用 `utility_formula_run` 跑一个内置公式，如 KDJ。

### 阶段 C：方法验证

成功标准：

- 把交易方法拆成公式、过滤器、买卖规则、仓位规则。
- 生成历史信号表。
- 跑至少 3 个年份或 3 个市场阶段。
- 输出收益/回撤/胜率/换手/样本数。

### 阶段 D：可视化复盘

成功标准：

- 用 `send_bt_data` 把买卖信号或净值序列送回通达信。
- 在通达信公式里用 `SIGNALS_TQ` 展示。
- 人工抽样 20 笔交易，确认信号位置没有错位。

### 阶段 E：盘中预警

成功标准：

- 只监控计划内股票。
- 只发提醒，不自动下单。
- 飞书提醒包含：代码、名称、触发规则、价格、证据、风险。

## 5. 推荐目录结构

```text
tdx-method-lab/
  formulas/
    method_x.tdx
  src/tdx_lab/
    data.py
    formulas.py
    signals.py
    backtest.py
    monitor.py
    execution.py
    risk.py
  notebooks/
  reports/
  docs/
    deepresearch-tdx-quant-system.md
  skills/
    tdxquant-mcp/
  vendor/
    tdxquant-mcp/
```

## 6. 风险和约束

### 6.1 Mac 约束

当前官方 TdxQuant 文档示例明显围绕桌面终端目录、`PYPlugins/user`、`TPythClient.dll` 和 Windows 路径。Mac App Store 里的通达信 iPad 兼容版大概率不足以提供 TdxQuant 的 `tqcenter.py` 和 DLL 依赖。

因此如果要完整使用 TdxQuant，实际可能需要：

- Windows 电脑或 Windows 虚拟机。
- 安装支持 TQ 策略功能的通达信金融终端/专业研究/量化模拟版。
- 通过局域网或本机 MCP SSE 给 Codex/OpenClaw 调用。

### 6.2 数据约束

- 数据需要终端登录和下载。
- 分钟线和日线缓存可能阻塞。
- 前复权数据要明确取数口径。
- 空结果必须当作连接/数据/参数问题处理，不能补猜。

### 6.3 交易约束

- 实盘自动下单不是默认能力，取决于券商版本和权限。
- 交易函数即使可用，也要保留人工确认。
- Agent 不应直接决定买卖，只能执行预设规则、生成提醒和复盘。

## 7. 对 Le 的建议

最短路线：

1. 不再纠结 Mac 版通达信，先确认能否拿到支持 TQ 的 Windows 终端。
2. 用量化模拟版或专业研究版搭 TdxQuant 环境。
3. 先接 `tdxquant-mcp`，只开放行情、财务、板块、公式、目录工具。
4. 把新交易方法公式化，先验证历史信号。
5. 跑出可接受统计结果后，再做盘中预警。
6. 实盘只做到“提醒 + 人工确认”，不要一开始做无人值守。

## 8. 下一步任务清单

等终端可用后，我建议按这个顺序推进：

1. 写 `src/tdx_lab/data.py`，封装 `market_get_kline` / `get_market_data`。
2. 写 `src/tdx_lab/formulas.py`，封装通达信公式调用。
3. 写一个 `scripts/smoke_test_tdx.py`：拉 5 根 K 线、跑 KDJ、查股票名称。
4. 把新交易方法整理成 `docs/method-spec.md`。
5. 为方法写第一版回测，不接交易接口。
6. 回测通过后，再做飞书提醒和通达信预警联动。

## 参考资料

- 通达信官方 TdxQuant 简介：https://help.tdx.com.cn/quant/
- 通达信官方安装终端与 `tqcenter.py` 说明：https://help.tdx.com.cn/quant/docs/markdown/mindoc-1cfsjkbf8f3is/mindoc-1d00kk3jsibbc.html
- 通达信官方 TQ 可获取数据范围：https://help.tdx.com.cn/quant/docs/markdown/mindoc-1ctuhthaq5qmg/
- 通达信官方策略示例、`send_warn`、`send_bt_data`：https://help.tdx.com.cn/quant/docs/markdown/gzh0122inweixinwenz/
- 通达信官方交易执行函数 `order_stock`：https://help.tdx.com.cn/quant/docs/markdown/mindoc-1h7k4iqb1grk4/mindoc-1h7k5j4drr928.html
- 通达信官方 FAQ：外部 Python 路径、公式 count、前复权口径：https://help.tdx.com.cn/quant/docs/markdown/mindoc-tdxpy.html
- 通达信官网导航：AI 平台、通达信 MCP、TdxClaw、Skills 广场：https://www.tdx.com.cn/
- tdxquant-mcp：https://github.com/lingfan/tdxquant-mcp
- tdxquant-mcp Agent 使用说明：https://github.com/lingfan/tdxquant-mcp/blob/main/docs/agent-usage.md

