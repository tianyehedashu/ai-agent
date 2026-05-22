# AI Gateway：Claude Code / Cursor 第三方客户端适配说明

> **数据基准**：2026-05  
> **读者**：运营配置、SRE 部署、后端维护  
> **快速上手**：[GATEWAY_THIRDPARTY_CLIENT_GUIDE.md](./GATEWAY_THIRDPARTY_CLIENT_GUIDE.md)（配置片段与 curl）  
> **部署**：[GATEWAY_DEPLOYMENT_CHECKLIST.md](./GATEWAY_DEPLOYMENT_CHECKLIST.md)  
> **领域架构**：[AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md)

---

## 1. 背景与目标

Claude Code、Cursor 等工具**不经过本仓库前端**，而是直接调用厂商原生协议（Anthropic Messages / OpenAI Chat Completions）。AI Gateway 需在**尽量少改客户端**的前提下提供：

| 目标 | 说明 |
|------|------|
| **协议兼容** | 保留 `/v1/messages`、`/v1/chat/completions` 等标准路径与请求体 |
| **鉴权统一** | 使用现有虚拟 Key（`sk-gw-*`），与 OpenAI/Anthropic SDK 的 Bearer / `x-api-key` 一致 |
| **模型可管** | 客户端 `model` 字符串必须在 Gateway 注册为 `GatewayModel.name`，并纳入 vkey 白名单 |
| **体验对齐** | 头透传、`count_tokens`、限流响应头、长连接/SSE，减少客户端报错与上下文估算失败 |
| **可观测** | 按客户端类型（`claude-code` / `cursor`）归因请求日志与大盘 |

**明确不在范围**：Claude Code 企业 SSO 自定义 OAuth（`/v1/oauth/authorize` 等）；网关仅支持 Bearer / `x-api-key` + `sk-gw-*`，对普通用户已足够。

---

## 2. 兼容性结论

### 2.1 虚拟 Key（vkey）

| 项目 | 结论 |
|------|------|
| 令牌形态 | `sk-gw-*`，与平台 `sk-*`（需 `gateway:proxy` scope + grant）二选一 |
| Claude Code | 推荐 `ANTHROPIC_AUTH_TOKEN=sk-gw-...`，`ANTHROPIC_BASE_URL` 指向网关根（无 `/v1` 尾段） |
| Cursor | Settings → Override OpenAI API Key：`sk-gw-...`；Base URL：`https://<host>/v1` |
| 白名单 | vkey 的 `allowed_models` 须包含客户端实际发送的 `model`；`allowed_capabilities` 含 `chat` |

鉴权实现见 `domains/gateway/presentation/deps.py`（`bearer_vkey_or_apikey_auth`）。

### 2.2 协议与端点

| 客户端 | 协议 | 网关路径 | 备注 |
|--------|------|----------|------|
| **Claude Code** | Anthropic Messages | `POST /v1/messages` | 支持流式 SSE |
| **Claude Code** | Token 计数 | `POST /v1/messages/count_tokens` | 跳过预算/限流，仅校验模型与白名单 |
| **Cursor** | OpenAI 兼容 | `POST /v1/chat/completions` | Base URL 必须带 `/v1` |
| 二者（可选） | 模型列表 | `GET /v1/models` | 用于自检；Anthropic 原生无列表端点 |

---

## 3. 网关已实现能力

### 3.1 入站 HTTP 头透传

客户端携带的协议扩展头会合并进 LiteLLM `extra_headers` 后转发上游：

| 头名 | 用途 |
|------|------|
| `anthropic-version` | Anthropic API 版本 |
| `anthropic-beta` | Beta 能力；与 Prompt Cache 中间件注入值**去重合并** |
| `openai-beta` | OpenAI Beta 头 |

**不透传**：`authorization`、`x-api-key`、`host`、`user-agent` 等（鉴权与网关控制面由网关重写）。

- 白名单逻辑：`presentation/proxy_header_passthrough.py`
- 逗号分隔合并：`domain/http_header_merge.py`

### 3.2 `POST /v1/messages/count_tokens`

Claude Code 用其做上下文窗口管理。网关行为：

- 校验 `model` 与 vkey 白名单、注册模型能力；
- **不**走预算预扣与 RPM/TPM 限流；
- 优先 `litellm.token_counter`，失败回退 `estimate_anthropic_request_tokens`。

实现：`ProxyUseCase.anthropic_count_tokens` → `anthropic_compat_router.py`。

### 3.3 限流响应头

成功响应附加厂商形限流头（只读 peek Redis 60s 窗口，不改变计数）：

| 风格 | 响应头前缀 |
|------|------------|
| OpenAI（Cursor） | `x-ratelimit-limit-requests`、`x-ratelimit-remaining-requests`、`x-ratelimit-reset-requests`；tokens 同理 |
| Anthropic（Claude Code） | `anthropic-ratelimit-requests-*`、`anthropic-ratelimit-tokens-*`（reset 为 ISO8601） |

- 协议格式（纯函数）：`domain/proxy_ratelimit_headers.py`
- 读 Redis + 编排：`application/proxy_rate_limit_headers.py` + `infrastructure/redis_rate_limit_usage_reader.py`
- CORS：`bootstrap/main.py` 的 `expose_headers` 已包含上述头名

### 3.4 客户端归因（可观测）

| 字段 | 来源 | 说明 |
|------|------|------|
| `client_ua` | `User-Agent`（截断 512） | 原始 UA |
| `client_type` | `infer_client_type(ua)` | `claude-code` / `cursor` / `openai-sdk` / `anthropic-sdk` / `unknown` |

- 推断规则：`domain/client_type.py`
- 落库：`gateway_request_logs.client_type`、`client_ua`（迁移 `20260520_gateway_request_log_client`）
- 大盘：`GET /api/v1/gateway/dashboard/summary` → `by_client_type`

### 3.5 入站护栏拆分（ProxyGuard）

校验、限流、预算、entitlement 预扣从 `ProxyUseCase` 抽到 **`ProxyGuard`**（`application/proxy_guard.py`），`proxy_chat_pipeline` 通过 `use_case.guard` 公开 API 调用，避免跨模块访问 `_check_*`。

`ProxyUseCase` 仍作为 `/v1/*` **编排门面**（LiteLLM 调用、响应适配、结算）。

---

## 4. 模型注册与别名

### 4.1 原则

1. **`GatewayModel.name` = 客户端 `model` 字段**（区分大小写，完全一致）。
2. **推荐别名清单**（运营最小集）：[`domains/gateway/domain/client_model_aliases.py`](../domains/gateway/domain/client_model_aliases.py)。
3. **Anthropic 4.6+**：dateless ID（如 `claude-opus-4-7`）为 **pinned 快照**；新版本以新 ID 发布，运营**追加**注册，勿删旧别名。
4. **上游 dated ID**：可用 `derive_client_facing_model_alias`（`domain/upstream_catalog_policy.py`）派生短别名后注册。

### 4.2 2026-05 推荐注册（摘要）

**Claude Code**（`ANTHROPIC_MODEL` / `ANTHROPIC_SMALL_FAST_MODEL`）：

| 用途 | 推荐 `GatewayModel.name` |
|------|---------------------------|
| 主模型（默认 opus） | `claude-opus-4-7`（CC v2.1.111+） |
| 平衡 | `claude-sonnet-4-6`、`claude-sonnet-4-5` |
| 小模型 / count_tokens | `claude-haiku-4-5` |
| 旧环境 | `claude-3-7-sonnet-latest`、`claude-3-5-haiku-latest` |

**Cursor**（Settings → Add Model）：

| 家族 | 示例 `GatewayModel.name` |
|------|---------------------------|
| OpenAI 前沿 | `gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini` |
| Anthropic | `claude-opus-4-7`、`claude-sonnet-4-6` |
| 其它 | `gemini-2.5-pro`、`composer-2.5`（按需） |

完整列表以代码中 `CLAUDE_CODE_ALIASES` / `CURSOR_ALIASES` 为准。

### 4.3 新版本 SOP

1. 在 `client_model_aliases.py` **追加**新 ID（不删旧项）。
2. 更新本文档与 [GATEWAY_THIRDPARTY_CLIENT_GUIDE.md](./GATEWAY_THIRDPARTY_CLIENT_GUIDE.md) 示例。
3. Gateway 后台注册模型并绑定凭据，或 `POST /api/v1/gateway/models/multi-credential`。
4. 将新别名加入相关 vkey 的 `allowed_models`。

---

## 5. Claude Code 接入

### 5.1 环境变量

```bash
export ANTHROPIC_BASE_URL="https://your-gateway.example.com"
export ANTHROPIC_AUTH_TOKEN="sk-gw-XXXXXXXX"
export ANTHROPIC_MODEL="claude-opus-4-7"
export ANTHROPIC_SMALL_FAST_MODEL="claude-haiku-4-5"
```

- `ANTHROPIC_BASE_URL`：**服务根**，不要加 `/v1`（Anthropic SDK 会拼 `/v1/messages`）。
- `ANTHROPIC_AUTH_TOKEN`：与 `Authorization: Bearer` / `x-api-key` 等价。

### 5.2 自检

```bash
claude --print "ping"
```

```bash
curl -s "https://your-gateway.example.com/v1/messages/count_tokens" \
  -H "x-api-key: sk-gw-XXXXXXXX" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-5","messages":[{"role":"user","content":"hi"}]}'
```

期望：`{"input_tokens": <正整数>}`。

---

## 6. Cursor 接入

### 6.1 设置步骤

1. **Settings → Models → Override OpenAI API Key**：`sk-gw-...`
2. **Override OpenAI Base URL**：`https://your-gateway.example.com/v1`（**必须**含 `/v1`）
3. **Add Model**：名称与 `GatewayModel.name` **完全一致**（如 `gpt-5.5`、`claude-opus-4-7`）
4. **Verify Models** → 期望 HTTP 200

### 6.2 说明

- Cursor 走 **OpenAI 兼容面**；Anthropic 模型名也需在网关中注册同名别名。
- 若 Verify 失败，优先查：模型未注册、不在 vkey 白名单、Base URL 漏 `/v1`。

---

## 7. 管理面前端

| 路径 | 内容 |
|------|------|
| `/gateway/guide` | 通用接入说明 + **#clients**「第三方客户端集成」（Claude Code / Cursor / SDK） |
| `/gateway/guide?key_id=<uuid>#clients` | 从虚拟 Key 页跳转并预选 Key |
| `/gateway/keys` | 创建 Key 对话框与列表行提供「打开指南」链接 |

实现：`frontend/src/pages/gateway/guide-client-integrations.tsx`、`guide-snippets.ts`（`buildClientIntegrations`）。

---

## 8. 部署与验证

生产环境须满足长连接、大 body、SSE 无缓冲，见 [GATEWAY_DEPLOYMENT_CHECKLIST.md](./GATEWAY_DEPLOYMENT_CHECKLIST.md)。

**建议验收项**：

| # | 项 | 命令/操作 |
|---|-----|-----------|
| 1 | Claude Code 非流式 | `claude --print "hello"` |
| 2 | Claude Code count_tokens | 见 §5.2 curl |
| 3 | Cursor Verify | Settings → Models → Verify |
| 4 | 流式 5 分钟 | `stream=true` 的 chat / messages |
| 5 | 限流头 | 响应含 `x-ratelimit-*` 或 `anthropic-ratelimit-*` |
| 6 | 日志归因 | 大盘 `by_client_type` 出现 `claude-code` / `cursor` |

---

## 9. 排错

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 401 | Key 无效/撤销 | 检查 `sk-gw-*` |
| 400 `model_not_allowed` | 未注册或 vkey 白名单未包含 | 注册 `GatewayModel` 并更新 vkey |
| 400 能力不匹配 | 模型 `capability` 非 `chat` | 注册时选 chat |
| 404 count_tokens | 网关版本过旧 | 升级含该路由的版本 |
| 429 | 预算/限流/套餐 | 查预算、entitlement；看 `Retry-After` |
| Cursor Verify 失败 | Base URL 无 `/v1` 或模型名不一致 | 对照 §6 |
| 流式中断 | 代理超时或缓冲未关 | 对照部署清单 nginx `proxy_buffering off` |
| 上下文计数偏差 | `token_counter` 失败走启发式 | 属预期回退；可查日志 |

---

## 10. 代码索引（维护用）

```
domains/gateway/
├── domain/
│   ├── client_model_aliases.py      # 推荐注册别名（2026-05）
│   ├── client_type.py               # UA → client_type
│   ├── http_header_merge.py         # anthropic-beta 等合并
│   ├── proxy_ratelimit_headers.py   # 限流响应头格式（纯函数）
│   ├── proxy_rate_limit_port.py     # RateLimitUsageReader 契约
│   └── upstream_catalog_policy.py   # derive_client_facing_model_alias
├── application/
│   ├── proxy_guard.py               # 入站护栏（公开 API）
│   ├── proxy_use_case.py            # 编排门面 + count_tokens
│   ├── proxy_chat_pipeline.py       # chat/messages 共用流水线
│   └── proxy_rate_limit_headers.py  # 限流头编排（读 Redis）
├── presentation/
│   ├── anthropic_compat_router.py   # /v1/messages、count_tokens
│   ├── openai_compat_router.py      # /v1/chat/completions
│   ├── proxy_header_passthrough.py  # 入站头白名单
│   └── proxy_request_context.py     # UA、透传、限流头
└── infrastructure/
    └── redis_rate_limit_usage_reader.py

frontend/src/pages/gateway/
├── guide.tsx
├── guide-client-integrations.tsx
├── guide-snippets.ts
└── keys.tsx

backend/docs/gateway/
├── GATEWAY_THIRDPARTY_CLIENT_GUIDE.md   # 速查配置
├── GATEWAY_DEPLOYMENT_CHECKLIST.md      # 部署
└── GATEWAY_CURSOR_CLAUDE_CODE.md        # 本文档
```

---

## 11. 相关迁移

| 迁移文件 | 说明 |
|----------|------|
| `alembic/versions/20260520_gateway_request_log_client.py` | `gateway_request_logs` 增加 `client_type`、`client_ua` |

部署后执行：`alembic upgrade head`。

---

## 12. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05 | 初版：Claude Code / Cursor 适配能力、模型别名 2026-05、ProxyGuard、Redis 限流头端口拆分 |
