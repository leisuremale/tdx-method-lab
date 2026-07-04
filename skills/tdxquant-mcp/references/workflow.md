# TdxQuant MCP：意图与工具（精简）

完整版见仓库 [`docs/agent-usage.md`](../../../docs/agent-usage.md)。

## 调用顺序

1. `tools_catalog`
2. 按需 `docs_get_tdxquant_intro`（讲平台背景时）
3. 具体业务工具（名称以 `tools_catalog` 为准）

## 意图对照

| 用户意图 | 常用工具 | 备注 |
|----------|-----------|------|
| K 线、Tick、历史行情 | `market_get_kline` | `period`：`1d` / `5m` / `tick` 等 |
| 实时快照、五档 | `market_get_snapshot` | 可能较慢 |
| 股票基础资料 | `stock_get_info` | |
| 扩展信息 | `stock_get_more_info` | |
| 板块列表 | `sector_list` | |
| 板块成分股 | `sector_stocks` | 需 `block_code` / `block_type` |
| 财务区间 / 报告期 | `financial_get_report_range` / `financial_get_report_by_date` | |
| 可转债 / 新股 | `cbipo_get_kzz_info` / `cbipo_get_ipo_info` | |
| 交易日 | `calendar_get_trading_calendar` | |
| 通达信公式 | `utility_formula_run` | `mode`：`zb` / `xg` / `exp` / `raw` |
| 刷新缓存 | `utility_refresh_cache` / `utility_refresh_kline` | 勿高频 |
| 平台简介 | `docs_get_tdxquant_intro` | Markdown正文 |

## 交易类（高风险）

- `trade_order_stock`、`trade_cancel_order_stock`、`trade_query_*`：默认 **dry-run**；仅在用户明确授权后才可关闭 dry-run。
- 账户句柄常需先 `trade_get_account_id`。

## 空结果

可能原因：未登录、未下载数据、代码格式错误、接口失败。勿编造数值。
