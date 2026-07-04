# 宿主 MCP 配置片段（TdxQuant SSE）

**服务前提**：本仓库根目录已 `uv sync --extra http`，`.env` 中配置 `TQ_PATH`、`MCP_HOST`、`MCP_PORT`，并已执行：

```bash
uv run python -m tdx_mcp.main_http
```

**SSE 端点**：`http://<MCP_HOST>:<MCP_PORT>/sse`  
示例：`http://127.0.0.1:8765/sse`

若客户端报错或无法连接，确认 URL **包含路径 `/sse`**（FastMCP 默认）。个别客户端若要求不同写法，以该客户端文档为准。

---

## Claude Code（远程 SSE）

在项目的 `.mcp.json` 或用户级 Claude Code MCP 配置中增加（名称可改）：

```json
{
  "mcpServers": {
    "tdxquant-sse": {
      "type": "sse",
      "url": "http://127.0.0.1:8765/sse"
    }
  }
}
```

也可使用 CLI（以 [Claude Code 官方文档](https://docs.claude.com/en/docs/claude-code/mcp) 为准）：

```bash
claude mcp add --transport sse tdxquant-sse http://127.0.0.1:8765/sse
```

---

## OpenClaw（`mcp.servers` 出站注册）

在 OpenClaw 配置文件（如 `~/.openclaw/openclaw.json`）的 `mcp.servers` 下增加；**未指定 `transport` 时默认按 SSE** 连接 `url`（见 [OpenClaw MCP文档](https://docs.openclaw.ai/cli/mcp)）。

```json
{
  "mcp": {
    "servers": {
      "tdxquant": {
        "url": "http://127.0.0.1:8765/sse"
      }
    }
  }
}
```

如需 **Streamable HTTP**，须服务端使用对应传输并在配置中设置 `"transport": "streamable-http"`；**当前本仓库 `main_http` 仅为 SSE**，勿混用。

敏感头可写在 `headers` 中；本服务默认本地无鉴权。

---

## Hermes（`~/.hermes/config.yaml`）

在 `mcp_servers` 下增加（缩进为 YAML）：

```yaml
mcp_servers:
  tdxquant:
    url: "http://127.0.0.1:8765/sse"
```

### 工具过滤（推荐）

缩小交易与缓存类暴露面，示例**仅允许行情与目录**（按需在 `include` 中扩展真实工具名）：

```yaml
mcp_servers:
  tdxquant:
    url: "http://127.0.0.1:8765/sse"
    tools:
      include:
        - tools_catalog
        - docs_get_tdxquant_intro
        - market_get_kline
        - market_get_snapshot
        - stock_get_info
      prompts: false
      resources: false
```

修改配置后在 Hermes 会话中执行 **`/reload-mcp`**。  
更多说明：[Use MCP with Hermes](https://hermes-agent.nousresearch.com/docs/guides/use-mcp-with-hermes)。

---

## 验证

连接成功后，在对话中让模型先调用 **`tools_catalog`**，确认返回分类与工具列表。
