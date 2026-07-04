# TDX Method Lab

独立测试库，用来验证另一个依赖通达信/TdxQuant 数据与公式能力的交易方法。

当前状态：准备阶段。现有 `stock-exchange` 方法论不在本库内修改。

## 候选连接层

优先候选：`tdxquant-mcp`

- 来源：https://github.com/lingfan/tdxquant-mcp
- 本地参考副本：`vendor/tdxquant-mcp`
- Skill 副本：`skills/tdxquant-mcp`
- 作用：把通达信 TdxQuant 的 `tqcenter` 能力封装成 MCP 工具，供 Agent 查询行情、K 线、财务、板块、通达信公式、交易日历等。

## 硬前提

必须先满足这些条件，才可能真实拉取通达信数据：

1. 本机已安装并能打开通达信/TdxQuant 终端。
2. 终端已登录并按官方说明完成数据/策略环境配置。
3. 能找到终端策略目录中的 `tqcenter.py`。
4. 已设置 `TQ_PATH`，指向可被 `tq.initialize(__file__)` 使用的策略脚本路径。

没有通达信终端时，本库只能准备接入文档和测试脚本，不能真实验证行情或公式。

## 下一步

等通达信终端装好后，按 `docs/tdxquant-mcp-readiness.md` 做自检。

