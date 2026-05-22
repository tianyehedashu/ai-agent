# Gateway 第三方协议客户端接入指南

> **完整说明（Claude Code / Cursor 适配沉淀）**：[GATEWAY_CURSOR_CLAUDE_CODE.md](./GATEWAY_CURSOR_CLAUDE_CODE.md)  
> 与 [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md) 配套；管理面交互见前端 `/gateway/guide`。

## 1. 前置条件

1. 在 **AI Gateway → 模型** 注册客户端将请求的 **别名**（`GatewayModel.name`），`capability=chat`。
2. 推荐别名见 [`domains/gateway/domain/client_model_aliases.py`](../domains/gateway/domain/client_model_aliases.py)（Claude Code / Cursor 常用列表，数据基准 **2026-05**）。
3. 创建 **虚拟 Key**（`sk-gw-*`），`allowed_models` 包含上述别名，`allowed_capabilities` 含 `chat`。
4. 上游探测得到 `claude-haiku-4-5-20251001`（Anthropic ≤4.5）或 `gpt-5.5-2026-04-23`（OpenAI snapshot）这类带日期的 id 时，可用 [`derive_client_facing_model_alias`](../domains/gateway/domain/upstream_catalog_policy.py) 派生 dateless 短别名后再行注册。

### 新版本上线时的运营动作

- **Anthropic 4.6+**（dateless ID 即 pinned 快照）：直接追加新 ID（如 `claude-opus-4-8`），不要覆盖旧 ID——老客户端可能仍在用。
- **Anthropic ≤4.5 / Cursor / OpenAI**：保留旧 ID + ``-latest`` alias，按需追加新 dated ID 与新 dateless ID。
- 在 Gateway 后台为新 ID 绑定 `provider_credentials` + `real_model`，或调用 `POST /api/v1/gateway/models/multi-credential` 一次性绑定多凭据。

## 2. Claude Code

```bash
export ANTHROPIC_BASE_URL="https://your-gateway.example.com"
export ANTHROPIC_AUTH_TOKEN="sk-gw-XXXXXXXX"
export ANTHROPIC_MODEL="claude-opus-4-7"             # 2026-05 当前默认 opus（v2.1.111+）
export ANTHROPIC_SMALL_FAST_MODEL="claude-haiku-4-5" # 标题/count_tokens 用
claude --print "hello"
```

- 协议：`POST /v1/messages`
- 鉴权：`x-api-key` 或 `Authorization: Bearer`（推荐 `ANTHROPIC_AUTH_TOKEN`）
- 上下文计数：`POST /v1/messages/count_tokens`（网关已实现）

## 3. Cursor

1. Settings → Models → **Override OpenAI API Key**：`sk-gw-...`
2. **Override OpenAI Base URL**：`https://your-gateway.example.com/v1`
3. **Add Model**：与 `GatewayModel.name` 完全一致（如 `gpt-5.5`、`gpt-5.4-mini`、`claude-opus-4-7`、`claude-sonnet-4-6`）
4. Verify → 期望 HTTP 200

## 4. OpenAI SDK / LangChain

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-gw-XXXXXXXX",
    base_url="https://your-gateway.example.com/v1",
)
client.chat.completions.create(
    model="gpt-5.5",
    messages=[{"role": "user", "content": "hi"}],
)
```

## 5. Anthropic SDK

```python
from anthropic import Anthropic

client = Anthropic(
    api_key="sk-gw-XXXXXXXX",
    base_url="https://your-gateway.example.com",
)
client.messages.create(
    model="claude-opus-4-7",
    max_tokens=64,
    messages=[{"role": "user", "content": "hi"}],
)
```

## 6. curl 自检

```bash
# Anthropic Messages（流式）
curl -N "https://your-gateway.example.com/v1/messages" \
  -H "x-api-key: sk-gw-XXXXXXXX" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-opus-4-7","max_tokens":32,"stream":true,"messages":[{"role":"user","content":"ping"}]}'

# OpenAI Chat
curl "https://your-gateway.example.com/v1/chat/completions" \
  -H "Authorization: Bearer sk-gw-XXXXXXXX" \
  -H "content-type: application/json" \
  -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"ping"}]}'
```

## 7. 排错

| HTTP | 含义 | 处理 |
|------|------|------|
| 401 | 鉴权失败 | 检查 sk-gw-* 是否有效、未撤销 |
| 400 model_not_allowed | 模型未注册或不在 vkey 白名单 | 注册 `GatewayModel` 并更新 vkey |
| 429 | 限流 / 套餐耗尽 | 查看预算与 entitlement；响应含 `Retry-After` |
| 404 count_tokens | 旧版本网关 | 升级至含 `/v1/messages/count_tokens` 的版本 |

## 8. 相关能力（实现侧）

- 入站头透传：`anthropic-version`、`anthropic-beta`（合并 Prompt Cache beta）、`openai-beta`
- 限流响应头：OpenAI `x-ratelimit-*` / Anthropic `anthropic-ratelimit-*`
- 可观测：`gateway_request_logs.client_type` / `client_ua`；大盘 `by_client_type` 切片
