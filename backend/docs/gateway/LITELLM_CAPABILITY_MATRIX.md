# LiteLLM 能力矩阵（本项目）

> **版本**：`litellm>=1.83.14`（见 `backend/pyproject.toml`）  
> **集成模式**：**Python SDK + Router 库**，**非** LiteLLM Proxy Server（不部署 `litellm --config` 独立进程）  
> **权威边界**：Gateway 域 `domains/gateway/`；Agent 域 **禁止** 直接 `import litellm`（见 `tests/architecture/test_agent_no_litellm_import.py`）  
> **相关文档**：[LLM_GATEWAY_ARCHITECTURE.md](./LLM_GATEWAY_ARCHITECTURE.md) · [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md) · [GATEWAY_PRICING_AND_LITELLM_COST.md](./GATEWAY_PRICING_AND_LITELLM_COST.md) · [LITELLM_SUPPORTED_MODELS.md](./LITELLM_SUPPORTED_MODELS.md)

---

## 1. 总览：LiteLLM 在本项目中的角色

```
┌─────────────────────────────────────────────────────────────────────────┐
│  客户端 / Agent                                                          │
│  · OpenAI SDK → /api/v1/openai/v1/*                                     │
│  · Anthropic SDK → /api/v1/anthropic/v1/messages                        │
│  · AgentLlmFacade → GatewayBridge（进程内 ProxyUseCase，不经 HTTP）        │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────┐
│  AI Gateway（自研 FastAPI）                                               │
│  · 鉴权 / 预算 / 限流 / 套餐 / 归因 / 下游定价 —— **LiteLLM 不提供**      │
│  · ProxyUseCase 编排 → metadata 注入 → 调用 LiteLLM                       │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
  litellm.Router          litellm.acompletion      litellm.callbacks
  (model_list 热加载)      / aembedding / …        (CustomLogger / Guardrail)
        │                       │
        └───────────┬───────────┘
                    ▼
            100+ Provider HTTP API
```

**设计取舍**：复用 LiteLLM 的**多 Provider 适配**、**Router 调度**、**成本估算**与**回调钩子**；虚拟 Key、团队预算、下游售价、请求日志持久化、PII 策略、Entitlement 套餐等由 Gateway 自研层承担，**不**使用 LiteLLM Proxy 的管理 UI / DB / Virtual Key 体系。

---

## 2. 能力矩阵（按 LiteLLM 能力域）

图例：**✅ 已用** · **◐ 部分用** · **❌ 未用** · **⛔ 刻意不用**

| # | LiteLLM 能力 | 状态 | 本项目用法 / 代码落点 | 说明 |
|---|-------------|------|----------------------|------|
| **A. SDK 调用面** |
| A1 | `completion` / `acompletion` | ✅ | `Router.acompletion`（`proxy_use_case.py`）；直连 `litellm.acompletion`（`proxy_litellm_client.py`） | Chat 主路径；流式 SSE 经 `adapt_stream` |
| A2 | `embedding` / `aembedding` | ◐ | `Router.aembedding`；DashScope **绕过** LiteLLM（`dashscope_embedding.py` + `perform_dashscope_embedding`） | LiteLLM 对 `dashscope` embedding 映射不完整，项目走 OpenAI 兼容端点直连 |
| A3 | `image_generation` / `aimage_generation` | ✅ | `Router.aimage_generation`（`proxy_non_chat_pipeline.py`） | HTTP：`POST .../v1/images/generations` |
| A4 | `transcription` / `atranscription` | ✅ | `Router.atranscription` | HTTP：`POST .../v1/audio/transcriptions` |
| A5 | `speech` / `aspeech` | ✅ | `Router.aspeech` / 直连降级 | HTTP：`POST .../v1/audio/speech`；二进制响应经 `adapt_binary_response` 结算 |
| A6 | `rerank` / `arerank` | ✅ | 直连 `litellm.arerank` | HTTP：`POST .../v1/rerank` |
| A7 | `moderation` / `amoderation` | ✅ | 直连 `litellm.amoderation` | HTTP：`POST .../v1/moderations` |
| A8 | `video_generation` / `avideo_generation` | ✅ | 直连 `litellm.avideo_generation` | HTTP：`POST .../v1/videos` |
| A9 | `anthropic_messages` | ✅ | `Router.aanthropic_messages` 或直连（`proxy_litellm_client.py`） | HTTP：`POST .../anthropic/v1/messages` |
| A10 | `text_completion`（Legacy） | ❌ | — | 未暴露 HTTP；项目仅 Chat Completions 形 |
| A11 | `responses` API（OpenAI Responses） | ❌ | — | LiteLLM 已支持部分 provider；Gateway 未接入 |
| A12 | `realtime` / WebSocket | ❌ | — | 未接入 |
| A13 | `batch` API | ❌ | — | 未接入 |
| A14 | `files` / Assistants / Threads | ❌ | — | 未接入 |
| A15 | `token_counter` | ✅ | `ProxyUseCase` 预估算 token（`proxy_use_case.py`） | 用于预算预扣与 Anthropic `count_tokens` |
| A16 | `completion_cost` | ✅ | `upstream_cost_resolver.py`、`pricing_display_cost.py`、流式兜底（`proxy_stream_settlement.py`） | 配合 `register_model` 与 deployment 级单价 |
| A17 | `get_model_info` / `supports_*` | ◐ | `litellm_capability_hint.py` + `litellm_capability_mapping.py` → `LitellmCapabilityHintAdapter`；`upstream_catalog_capability_prep.py`（正则目录） | **写侧 + 探测** hint（vision/tools/json/reasoning/image_gen）；配置托管种子跳过；`PATCH resync_capabilities` / 批量导入经目录 SSOT 重算 |
| **B. Router** |
| B1 | `Router(model_list=…)` | ✅ | `router_singleton.py` → `get_router` / `reload_router` | 启动 warm-up + 管理面变更后 `set_model_list` |
| B2 | `routing_strategy` | ✅ | 6 种（`domain/types.RoutingStrategy`） | 全局单策略：取 DB 路由表最高频；默认 `simple-shuffle`；`weighted-pick` 映射到 LiteLLM `simple-shuffle` |
| B2a | `simple-shuffle` | ✅ | 默认 / 种子路由 | 随机；若 deployment 带 `weight` 则加权随机 |
| B2f | `weighted-pick` | ✅ | 管理面可配 | 使用 `GatewayModel.weight` 做加权随机，底层复用 LiteLLM `simple-shuffle` |
| B2b | `least-busy` | ✅ | 管理面可配 | |
| B2c | `latency-based-routing` | ✅ | 管理面可配 | |
| B2d | `usage-based-routing-v2` | ✅ | 管理面可配 | |
| B2e | `cost-based-routing` | ✅ | 管理面可配 | 依赖 deployment `input_cost_per_token` 等注入（`router_singleton._PRICING_INJECT_KEYS`） |
| B3 | `fallbacks` | ✅ | `GatewayRoute.fallbacks_general` → Router `fallbacks` | |
| B4 | `content_policy_fallbacks` | ✅ | `fallbacks_content_policy` | 内容策略类失败切换 |
| B5 | `context_window_fallbacks` | ✅ | `fallbacks_context_window` | 上下文超长切换 |
| B6 | `num_retries` | ✅ | 固定 `2`（`router_singleton._build_router_kwargs`） | |
| B7 | `allowed_fails` + `cooldown_time` | ✅ | `gateway_router_cooldown_threshold` / `gateway_router_cooldown_seconds` | deployment 冷却 |
| B8 | `redis_url`（跨进程 cooldown/TPM/RPM） | ✅ | `gateway_router_redis_url` 或 `redis_url` | 多 worker 共享 Router 状态 |
| B9 | `enable_pre_call_checks` | ✅ | 固定 `True` | 与 ProviderQuotaGuard 配合 |
| B10 | deployment `rpm` / `tpm` | ✅ | 来自 `GatewayModel.rpm_limit` / `tpm_limit` | 写入 `litellm_params`；Anthropic 直连时会剔除（`filter_litellm_params_for_direct_anthropic`） |
| B11 | deployment `weight` | ✅ | `GatewayModel.weight` → `litellm_params.weight` + `model_info.weight` | `litellm_params.weight` 影响 shuffle 权重；`model_info.weight` 用于展示/归因 |
| B12 | `add_deployment` / `delete_deployment` | ◐ | 主要用 `set_model_list` 全量热更 | 未逐条增量 API |
| B13 | Router `a*` 以外的能力 | ◐ | 见 A5–A8：部分走直连 SDK | speech/rerank/moderation/video 未统一经 Router |
| B14 | Tag-based routing / Auto routing | ❌ | — | LiteLLM 高级路由；项目用自研 `GatewayRoute` + fallback 三类 |
| B15 | Priority / Budget routing（Router 内置） | ⛔ | 自研 `BudgetService` + `EntitlementGuard` | 不用 LiteLLM 内置 budget limiter |
| **C. 回调与可观测** |
| C1 | `litellm.callbacks` 全局注册 | ✅ | `ensure_gateway_callbacks()`（`router_singleton.py`） | Router 与直连共用 |
| C2 | `CustomLogger` | ✅ | `GatewayCustomLogger`（`callbacks/custom_logger.py`） | `async_log_success_event` / `async_log_failure_event` |
| C3 | StandardLoggingPayload / `_hidden_params` | ◐ | 读 `response_cost`、usage（`cost_calculation.py`） | 写入 `gateway_request_logs` + Redis 实时计数 |
| C4 | `success_callback` / `failure_callback` 全局列表 | ❌ | conftest 测试里清空 | 项目用 `callbacks` 而非 legacy 列表 |
| C5 | Langfuse / MLflow / Helicone / Datadog 等集成 | ❌ | — | LiteLLM 内置 observability 集成未启用 |
| C6 | OpenTelemetry | ❌ | — | |
| C7 | `async_post_call_streaming_hook` | ◐ | CustomLogger 空实现 | 流式成本靠末帧 success_event + `proxy_stream_settlement` |
| C8 | `async_dataset_hook` | ◐ | 空实现 | Gateway 不落 LiteLLM dataset |
| **D. Guardrails** |
| D1 | `CustomGuardrail` | ✅ | `GatewayPiiGuardrail`（`guardrails/pii_guardrail.py`） | 默认关：`gateway_default_guardrail_enabled=False` |
| D2 | LiteLLM 内置 Presidio / Bedrock Guardrails | ❌ | — | |
| D3 | Guardrails AI 集成 | ❌ | — | |
| D4 | Moderation 作为 guardrail | ❌ | 独立 HTTP `/moderations` | |
| **E. 定价与成本** |
| E1 | `litellm.model_cost` 内置价目 | ✅ | `import litellm` 时已加载（约 2700+ 行）；启动不再重注册全量 | 仅作 `completion_cost` 兜底 |
| E2 | `litellm.register_model()` | ✅ | `PricingService.sync_to_litellm_registry(only_keys=...)` 增量注册 | 管理面写入按 key 触发；进程内指纹缓存避免重复 |
| E3 | `LitellmUpstreamPriceSyncService` | ✅ | `pricing/litellm_upstream_price_sync.py` | 从 `model_cost` 同步到 DB，`manual` 行受保护 |
| E4 | Prompt cache 单价字段 | ✅ | `cache_creation_input_token_cost` / `cache_read_input_token_cost` | Router deployment + 注册表 |
| E5 | Provider margin（Proxy 加价） | ⛔ | 用 `downstream_model_pricing` 双账 | 见 GATEWAY_PRICING 文档 §禁止项 |
| E6 | 图像/音频按次计费字段 | ◐ | 依赖 LiteLLM 注册；Gateway 以 token 为主 | 非 token 能力结算精度因模型而异 |
| **F. LiteLLM Proxy Server（独立产品）** |
| F1 | `litellm --config` / Admin UI | ❌ | — | 管理面为自研 `/api/v1/gateway/*` |
| F2 | Proxy Virtual Keys / Teams / Users | ❌ | 自研 `gateway_virtual_keys` | |
| F3 | Proxy Budget / Rate limit | ❌ | 自研 Redis + `BudgetService` | |
| F4 | Proxy Model Management DB | ❌ | 自研 `gateway_models` / `gateway_routes` | |
| F5 | Proxy SSO / SCIM | ❌ | 自研 Identity JWT | |
| F6 | Proxy Spend Logs UI | ❌ | 自研 logs / dashboard | |
| F7 | Proxy MCP Gateway / A2A Agents | ❌ | Agent 域自研 MCP | LiteLLM 1.x 已支持，本项目未用 |
| F8 | Proxy Pass-through endpoints | ❌ | — | |
| **G. Provider 与凭据** |
| G1 | Provider 前缀约定 | ✅ | `build_litellm_model_id()`（`domain/litellm_model_id.py`） | `zhipuai`→`zai/`；`dashscope|deepseek|volcengine|anthropic` 加前缀 |
| G2 | `api_key` 参数名映射 | ✅ | `litellm_api_key_param_name` | Bedrock → `aws_access_key_id` |
| G3 | `extra` 字段白名单透传 | ✅ | `litellm_credential_extra_keys.py` | 与前端 `provider-schemas.ts` 对齐 |
| G4 | 种子目录 Provider | ✅ | `gateway-catalog.seed.json` | deepseek, dashscope, zhipuai, openai, anthropic, volcengine |
| G5 | 凭据 UI 声明但未种子化的 Provider | ◐ | `litellm_credential_extra_keys` 白名单 | azure, bedrock, gemini, vertex_ai, cohere, mistral, fireworks, together_ai — **可配凭据，无默认种子** |
| G6 | LiteLLM 支持的 100+ Provider | ◐ | 理论上凭据 + model_id 即可 | 未逐一验收；见 [LITELLM_SUPPORTED_MODELS.md](./LITELLM_SUPPORTED_MODELS.md) 中国区实测 |
| **H. 参数与能力适配（Gateway 自研，非 LiteLLM 内置）** |
| H1 | Tools / JSON mode / Vision | ✅ | `ModelCapabilitySnapshot` + `UpstreamAdapter` | tags 驱动；出站前 `apply_invocation_kwargs` |
| H2 | Reasoning / thinking 参数 | ✅ | `thinking_param.py`、`invocation_policy.py` | DeepSeek reasoner、Anthropic extended thinking 等 |
| H3 | Prompt Cache 注入 | ✅ | `prompt_cache_middleware.py` | Anthropic / DeepSeek / OpenAI；**非** LiteLLM 内置 middleware |
| H4 | Temperature 策略 | ✅ | `temperature_policy.py` | reasoning 模型禁温度等 |
| H5 | DashScope embedding 直连 | ✅ | 绕过 LiteLLM | 见 A2 |
| H6 | Volcengine 图像生图 | ✅ | `volcengine_image.py` + `router_deployment_params` + `proxy_litellm_client` | 探活与 `POST .../images/generations` 直连方舟；非 LiteLLM ``aimage_generation`` |
| **I. 架构约束** |
| I1 | Agent 域禁止 import litellm | ✅ | `test_agent_no_litellm_import.py` | 必须经 `GatewayProxyProtocol` |
| I2 | 内部桥接禁止静默直连 | ✅ | `gateway_proxy_disable_internal_direct_litellm=True`（默认） | system vkey 未注册模型时可例外直连 |
| I3 | 双进程 Router 一致性 | ✅ | Redis + `reload_router` | 管理写操作后热更 |

---

## 3. HTTP 入口 ↔ LiteLLM API 对照

| Gateway HTTP | `GatewayCapability` | LiteLLM 调用路径 | 经 Router? |
|--------------|---------------------|------------------|------------|
| `POST .../openai/v1/chat/completions` | `chat` | `router.acompletion` / `acompletion` 直连 | 通常 ✅；internal direct 时 ❌ |
| `POST .../anthropic/v1/messages` | `chat` | `router.aanthropic_messages` / `anthropic_messages` | 通常 ✅ |
| `POST .../openai/v1/embeddings` | `embedding` | `router.aembedding` / DashScope 直连 / `aembedding` | 混合 |
| `POST .../openai/v1/images/generations` | `image` | `router.aimage_generation` | ✅ |
| `POST .../openai/v1/audio/transcriptions` | `audio_transcription` | `router.atranscription` | ✅ |
| `POST .../openai/v1/audio/speech` | `audio_speech` | `router.aspeech` / `aspeech` 直连 | 通常 ✅ |
| `POST .../openai/v1/rerank` | `rerank` | `router.arerank` / `arerank` 直连 | 通常 ✅ |
| `POST .../openai/v1/moderations` | `moderation` | `router.amoderation` / `amoderation` 直连 | 通常 ✅ |
| `POST .../openai/v1/videos` | `video_generation` | `router.avideo_generation` / `avideo_generation` 直连 | 通常 ✅ |
| `GET .../openai/v1/models` | — | **不调用 LiteLLM** | 读 DB 合并列表（`gateway_model_listing`） |
| Agent `GatewayBridge.chat_completion` | `chat` | 同 chat completions | 同左 |
| Agent `GatewayBridge.embedding` | `embedding` | 同 embeddings | 同左 |
| Agent `EmbeddingService(local)` | — | **不调用 LiteLLM** | FastEmbed 本地向量 |

---

## 4. Router `model_list` 装配细节

每条 deployment 来源：`GatewayModel` / `SystemGatewayModel`（单模型）或 `GatewayRoute.virtual_model`（多 deployment 负载均衡）。

```
GatewayModel.name = "qwen-plus"
        │
        ▼
model_name = encode_router_model_name(team_id, name)
           → "gw/t/{tenant_uuid}/qwen-plus"  或  "gw/s/{name}"
        │
        ▼
litellm_params.model = build_litellm_model_id(provider, real_model)
           → e.g. "dashscope/qwen-plus"
        │
        ▼
litellm_params.api_key / api_base / rpm / tpm / input_cost_per_token / …
        │
        ▼
model_info = { id, team_id, capability, gateway_credential_id, … }
           → ProviderQuotaGuard pre-call 读 credential_id
           → GatewayCustomLogger 写 request log
```

**路由冲突规则**：若 `GatewayModel.name` 与 `GatewayRoute.virtual_model` 同名，**Model 行优先**，Route 仅作 fallback 图（`router_singleton._routes_to_virtual_deployments`）。

**全局 routing_strategy**：LiteLLM Router 单例只能绑定一个策略；项目取所有 active route 的 **最高频** `strategy` 字段，而非 per-route 策略。

---

## 5. 回调链（一次 Chat 请求的 LiteLLM 侧）

```
ensure_gateway_callbacks()
  ├─ GatewayCustomLogger          → 成功/失败落库、Redis 计数、采样
  ├─ ProviderPlanPreCallLogger    → async_pre_call_hook（provider_plan_guard.py）：
  │     ① 成员+凭据+模型 平台预算（Phase2，部署已选）→ maybe_reserve_user_credential_budget
  │     ② 上游厂商套餐预扣（ProviderPlan）
  └─ GatewayPiiGuardrail (可选)   → async_pre_call_hook 脱敏

Router.acompletion / acompletion
  → Provider HTTP
  → async_log_success_event / async_log_failure_event
  → ProxyResponseAdapter 结算 budget / entitlement（Gateway 层，非 LiteLLM）
  → Phase2 结算：commit_user_credential_budget（成功）/ release（失败）
```

**两阶段平台预算**：
- **Phase1（入站 preflight）**：`ProxyGuard.check_budget` 扫描 `credential_id IS NULL` 的 system/tenant/user/key 维度（含成员总量、成员+模型）。
- **Phase2（`async_pre_call_hook`，部署选定后）**：按 Router 注入的 `gateway_user_id` / `gateway_credential_id` / `gateway_model_name` 命中「成员+凭据+模型」专属预算（`gateway_budgets.credential_id`）。先存在性索引 `gw:budget_uc:{user_id}` 快路径排除无规则用户，命中才走 `budget_config_cache` + Redis 预扣。

**失败语义差异（重要）**：Phase2 耗尽抛 `BudgetExceededError` → HTTP 429，**不**进入 ProviderPlan、**不**触发 Router cooldown/fallback（否则会绕过成员限额换 deployment）；而 `ProviderPlanExhaustedError` 才触发 fallback。

**personal team 豁免**：命中个人工作区注册模型（`record.tenant_id == 个人团队`）时，preflight 跳过 Phase1，且因无团队预算/索引而天然跳过 Phase2。

**流式**：metadata 设 `gateway_defer_cost_settlement=True`，避免 proxy 与 callback 双计；末帧由 callback + `proxy_stream_settlement` 兜底；Phase2 结算以 `request_id` 幂等。

---

## 6. 定价：LiteLLM 与 Gateway 分工

| 步骤 | LiteLLM | Gateway |
|------|---------|---------|
| 单价来源 | `model_cost` + `register_model` | `upstream_model_pricing` 表 + 启动 sync |
| 运行时选用 | deployment / 注册表单价 → `response_cost` | 读 `_hidden_params` 写入 `cost_usd` |
| 对客户售价 | — | `downstream_model_pricing` → `revenue_usd` |
| 价目同步 | — | `LitellmUpstreamPriceSyncService`（`source=litellm_fallback`） |
| 展示估算 | `completion_cost()` | `PricingService.calculate()` + 前端 `estimateUsageCostDisplay` |

---

## 7. LiteLLM 有、本项目未用的能力（选型参考）

以下能力在 [LiteLLM 文档](https://docs.litellm.ai/docs/) 中可用，**当前代码无集成**；若未来需要，应优先评估是否仍保持「库模式」而非引入完整 Proxy。

| 类别 | 代表能力 | 未用原因 / 替代 |
|------|----------|----------------|
| **部署形态** | LiteLLM Proxy + Admin UI | 已有 FastAPI Gateway + 自研管理面 |
| **身份与配额** | Proxy Virtual Keys、Team budgets | 自研 vkey / budget / entitlement |
| **可观测** | Langfuse、MLflow、Helicone、OTel 插件 | 自研 `gateway_request_logs` + Redis metrics |
| **Guardrails** | Presidio、Bedrock Guardrails、Guardrails AI | 仅自研 PII CustomGuardrail |
| **API 面** | Responses API、Realtime、Batch、Assistants | 无 HTTP 路由；Agent 用 Chat Completions |
| **路由高级** | Auto Router、Tag routing、Semantic routing | 自研 Route + 三类 fallback |
| **Skills / Agent** | litellm-skills、MCP Gateway、A2A | Agent 域自研 MCP；未走 LiteLLM Agent 网关 |
| **缓存** | LiteLLM Redis caching / S3 caching | 自研 Prompt Cache middleware（消息级 cache_control） |
| **Mock** | `mock_completion` / 测试桩 | 测试用 monkeypatch / 集成测真 API |
| **Fine-tuning** | Fine-tune job API | 未涉及 |
| **Passthrough** | 原样转发 provider 特殊端点 | 未实现 |

---

## 8. 环境变量与开关（LiteLLM 相关）

| 配置项 | 默认 | 作用 |
|--------|------|------|
| `gateway_proxy_disable_internal_direct_litellm` | `True` | 禁止 system vkey 绕过 Router 直连 |
| `gateway_default_guardrail_enabled` | `False` | 是否注册 PII CustomGuardrail |
| `gateway_router_redis_url` | `None`（回退 `redis_url`） | Router 跨 worker 状态 |
| `gateway_router_cooldown_threshold` | `5` | → Router `allowed_fails` |
| `gateway_router_cooldown_seconds` | `60` | → Router `cooldown_time` |
| `gateway_catalog_sync_on_startup` | `False` | 启动时完整目录维护（seed→DB、审计、`reload_router`）；默认关闭，DB 价目由管理面写入路径按 key 增量注册到 LiteLLM |

Provider API Key **不**再放在全局 `settings.*_api_key`（Agent 架构测试禁止读取）；一律经 Gateway 凭据表加密存储。

---

## 9. 已知缺口与变通

| 现象 | 原因 | 项目处理 |
|------|------|----------|
| DashScope embedding 报错 | LiteLLM provider 映射不完整 | 默认 OpenAI 兼容 `/embeddings` 直连；可选 `gateway_dashscope_embedding_via_litellm=true` |
| `aspeech` / `arerank` 等不经 Router | ~~历史实现~~ | **已统一**经 `Router.a*` + internal direct 降级（见 §3） |
| 虚拟模型名无 `model_cost` | LiteLLM 内置表键为 upstream id | `register_model` + deployment 单价注入 |
| Anthropic 直连带 rpm/tpm | 非 Messages API 参数 | `filter_litellm_params_for_direct_anthropic` 剔除 |
| Claude Code `context_management` / `thinking` 等 | 跨协议转译到非 Anthropic 上游 | **两层策略**：① domain `anthropic_only_request_fields.strip_anthropic_only_fields`（按 `gateway_provider` 显式剥离 + warning 日志）；② `ensure_gateway_callbacks` 设置 `litellm.drop_params=True` 兜底未纳入清单的字段 |
| 多 worker 策略不一致 | 单例 + 热更 | Redis + 写后 `reload_router` |
| LiteLLM 版本升级 | `model_cost` / provider 行为变化 | 跑 `test_litellm_upstream_price_sync`、集成测、`scripts/probe_dashscope_embedding.py` |

### DashScope embedding 切换 Runbook

1. 升级 `litellm` 依赖  
2. 运行 `uv run python scripts/probe_dashscope_embedding.py`（需 `DASHSCOPE_API_KEY`）  
3. 若 PASS → staging 设 `GATEWAY_DASHSCOPE_EMBEDDING_VIA_LITELLM=true`  
4. 跑 `tests/unit/gateway/test_proxy_dashscope_embedding.py` 与 embedding 集成测  
5. 稳定后可评估移除 `dashscope_embedding_client`（单独 PR）

---

### 跨协议字段剥离策略（Anthropic Messages → 非 Anthropic 上游）

当 Claude Code / Anthropic SDK 走 `POST /v1/messages`，但 `GatewayModel.provider`
为 `volcengine` / `openai` / `dashscope` 等非 Anthropic 上游时，请求体里的 Anthropic
私有字段无法被 LiteLLM 跨协议转译，默认会抛 `UnsupportedParamsError`。

**按字段语义分配到合适的处理层**（避免一刀切"无脑丢"误伤运营声明的能力）：

| 字段 | 处理层 | 粒度 | 决策依据 |
|------|--------|------|----------|
| `thinking` / `enable_thinking` | `domain/policies/invocation_policy.py::apply_invocation_kwargs`（经 `UpstreamAdapter`） | **模型**粒度 | `GatewayModel.tags["thinking_param"]`：`anthropic_extended` 保留顶层 `thinking`；`deepseek_v4_thinking` 将 Claude Code 顶层 `thinking` 译为 `extra_body.thinking`；`dashscope_enable_thinking` 翻译；`builtin_reasoning` / `none` 剥离 |
| `context_management` / `anthropic_version` / `anthropic_beta` | `domain/policies/anthropic_only_request_fields.py` | **provider** 粒度（可被模型 tags 例外） | 默认非 Anthropic 上游剥离；`tags["anthropic_messages_field_policy"]="native"` 全量透传；`tags["preserve_anthropic_fields"]` 字段级保留 |
| 其它未来字段 | `litellm.drop_params=True`（`ensure_gateway_callbacks`） | LiteLLM 内部白名单 | 任何未纳入上述策略的不兼容字段兜底 |

**application 编排**：`proxy_chat_entries.py::_strip_anthropic_only_fields_for_non_anthropic_upstream`
在 `anthropic_messages` 入口调 domain 策略原地剥离 + `logger.warning` 写
`request_id` / `dropped_fields` / `upstream_provider`，保证剥离可观测。

**为什么 `thinking` 不进 provider 粒度清单**：项目早已建立 `thinking_param` 体系
（见 `domain/thinking_param.py`、`invocation_policy.py`）按 **模型粒度** 处理思考开关。
若把 `thinking` 加进 provider 粒度清单，会**盖过模型级配置**——例如运营给某非 Anthropic
上游显式声明 `thinking_param = "anthropic_extended"`（认为该上游能消费 Anthropic 格式
的 thinking 字段）时，请求会被错误剥离。

**新字段加入清单前必查**：

1. 该字段是否已有**模型粒度**的能力体系？（如 `thinking_param`、`temperature_policy`）
   → 优先扩展该体系，**不要** 进本清单；
2. 该字段是否在某些 provider 上**有跨协议翻译能力**？
   → 在 `UpstreamAdapter` 做字段名/语义翻译，**不要** 进本清单；
3. 仅当**完全无跨 provider 等价**且**无既有体系**时，才进 `ANTHROPIC_ONLY_REQUEST_FIELDS`。

**模型 tags 运营配置**（`GatewayModel.tags`，无需改代码）：

| Tag | 值 | 效果 |
|-----|-----|------|
| `anthropic_messages_field_policy` | `"native"` | 非 Anthropic 上游也**不剥离**清单内字段（上游兼容 Anthropic Messages 形态） |
| `anthropic_messages_field_policy` | `"strip"` 或省略 | 默认：非 Anthropic 上游剥离清单内字段 |
| `preserve_anthropic_fields` | `["context_management", ...]` | 仅保留列出的字段，其余清单字段仍剥离 |

示例：某 volcengine 模型已支持 `context_management` 时：

```json
{
  "preserve_anthropic_fields": ["context_management"]
}
```

单测：`tests/unit/gateway/domain/test_anthropic_only_request_fields.py` 覆盖所有分支

## 10. 维护清单

**改 LiteLLM 相关行为时必查：**

1. 新 **业务规则** → `domains/gateway/domain/`（policy / errors），非 UseCase 内裸 if  
2. 新 **出站调用** → `proxy_litellm_client.py` 或 `proxy_non_chat_pipeline.py`  
3. 新 **Provider extra 字段** → `litellm_credential_extra_keys.py` + 前端 provider schema  
4. 新 **模型 ID 规则** → `litellm_model_id.py` + `litellm_real_model_prefix.py`  
5. 新 **回调** → `ensure_gateway_callbacks()`，禁止仅挂 Router 不挂直连  
6. **测试**：`tests/unit/gateway/test_*` + `tests/architecture/test_agent_no_litellm_import.py`

**推荐命令（`backend/`）：**

```powershell
uv run pytest tests/unit/gateway/test_litellm_upstream_price_sync.py tests/unit/gateway/test_router_singleton_guardrail.py -q
uv run pytest tests/architecture/test_agent_no_litellm_import.py -q
uv run python scripts/test_litellm_models.py   # 需配置 API Key
```

---

## 11. 文档索引

| 文档 | 内容 |
|------|------|
| 本文 | LiteLLM **能力矩阵** + 项目用/未用对照 |
| [LITELLM_SUPPORTED_MODELS.md](./LITELLM_SUPPORTED_MODELS.md) | 中国区 Provider **实测**模型列表 |
| [GATEWAY_PRICING_AND_LITELLM_COST.md](./GATEWAY_PRICING_AND_LITELLM_COST.md) | 成本计算链路 |
| [GATEWAY_COMPATIBILITY_CHECK.md](../archive/gateway/GATEWAY_COMPATIBILITY_CHECK.md) | Agent 与 Gateway 类型兼容（归档） |
| [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md) | Gateway 域 DDD 分层 |

---

*最后更新：2026-05-22 · 对齐 `litellm>=1.83.14` 与当前 `domains/gateway` 代码结构。*
