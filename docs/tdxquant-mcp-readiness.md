# TdxQuant MCP 接入准备

## 结论

目前找到的最贴近需求的方案是 `TdxQuant MCP`：

- 官方底座：通达信 TdxQuant，基于通达信金融终端和 `tqcenter`。
- 第三方封装：`lingfan/tdxquant-mcp`，提供 MCP 服务和 Agent Skill。
- 能力覆盖：行情、K 线/Tick、快照、股票资料、板块、财务、可转债/新股、交易日历、通达信公式、交易查询/下单预览。

## 官方能力依据

通达信官方帮助说明，TdxQuant 是基于通达信金融终端构建的 Python 量化策略运行框架，通过 API 提供行情数据获取和交易指令执行能力。

官方文档还列出 TQ 可获取的数据范围：股票、基金、指数、行业/概念/风格板块、期货、宏观、可转债、期权、特定数据文件包。

## 本库已准备

- 已创建独立 repo：`tdx-method-lab`
- 已克隆候选连接器：`vendor/tdxquant-mcp`
- 已复制 Agent Skill：`skills/tdxquant-mcp`
- 已确认本机有 `uv`
- 已用 `redskill search 通达信/tdx/TdxQuant` 搜索，未找到匹配 skill

## 装好通达信后的自检顺序

以下命令在本库根目录执行：

```bash
cd /Users/lijingyan/.openclaw/workspace-xiao-hong/tdx-method-lab/vendor/tdxquant-mcp
```

创建 `.env`，填入真实路径：

```bash
cp .env.example .env
```

需要人工编辑 `.env`：

```text
TQ_PATH=/path/to/tdx/PYPlugins/user/tdxdata_test.py
MCP_HOST=127.0.0.1
MCP_PORT=8765
```

安装依赖：

```bash
uv sync --extra http
```

启动 MCP：

```bash
uv run python -m tdx_mcp.main_http
```

如果启动成功，Agent 侧应先调：

```text
tools_catalog
```

然后用最小行情请求验证：

```text
market_get_kline stock_list=["600519.SH"] period="1d" count=5 dividend_type="none"
```

## 风险边界

- 没有工具返回时，不编造行情和财务数据。
- 交易类工具保持 `dry_run=true`。
- 任何真实下单或撤单都必须由 Le 明确授权，并再次确认。
- 本测试库只验证新方法，不回写 `stock-exchange` 的现有交易系统。
