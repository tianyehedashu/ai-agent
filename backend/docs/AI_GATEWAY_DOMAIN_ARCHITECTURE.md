# AI Gateway 领域架构与工程实践

> **适用范围**：`domains/gateway`、`domains/tenancy`（团队/成员权威）、`domains/gateway/application`（内部桥接端口与辅助）、**OpenAI 兼容与 Anthropic Messages（`/v1/*`）** 对外入口、管理 API、内部 LLM 桥接及相关前端。  
> **更新说明**：LiteLLM 选型见 [LLM_GATEWAY_ARCHITECTURE.md](./LLM_GATEWAY_ARCHITECTURE.md)；兼容性见 [GATEWAY_COMPATIBILITY_CHECK.md](./GATEWAY_COMPATIBILITY_CHECK.md)。

---

## 1. 架构定位

| 维度 | 说明 |
|------|------|
| **业务目标** | 统一多模型调用入口（LiteLLM Router）、团队/虚拟 Key、凭据池、预算与限流、可观测（日志/告警/rollup）。 |
| **边界** | **Inbound**：根路径 **`/v1/*`** —— **OpenAI 兼容**（如 `POST /v1/chat/completions`）与 **Anthropic Messages**（`POST /v1/messages`）；鉴权为 **`Authorization: Bearer`** 或 **`x-api-key`**（Bearer 优先），令牌为 **`sk-gw-*` 虚拟 Key** 或带 **`gateway:proxy`** scope 的 **`sk-*`**（后者需配合 **`X-Team-Id`** 解析团队）。**管理面**：`/api/v1/gateway/*`（JWT + 团队上下文）。**Outbound**：各 Provider HTTP API（由 LiteLLM 发起）。 |
| **与 Agent 域关系** | Agent 通过 `LLMGateway` + `GatewayProxyProtocol`（`domains/gateway/application/ports.py`）可走内部桥接，归因到 personal team 与系统 vkey 池。 |

---

## 2. 分层结构（DDD + CQRS）

```
domains/tenancy/                  # 团队与成员：权威 ORM 与 TeamService（Gateway / Identity 经此域）
├── application/
│   ├── team_service.py
│   └── management_team_resolve_use_case.py  # 管理面团队上下文（MembershipPort）
├── domain/management_context.py   # ManagementTeamContext；`gateway.domain.types` 再导出以保持既有 import
├── presentation/
│   ├── team_dependencies.py       # CurrentTeam / RequiredTeam*（管理面依赖）
│   ├── teams_router.py            # /teams* HTTP（前缀在 bootstrap 挂载为 /api/v1/gateway）
│   └── schemas/teams.py
└── infrastructure/
    ├── membership_adapter.py      # MembershipPort 实现
    ├── models/team.py
    └── repositories/team_repository.py

domains/gateway/
├── presentation/                 # HTTP：路由、Schema、依赖；禁止直连仓储
│   ├── http_error_map.py       # 领域异常 → HTTPException
│   ├── deps.py                 # 鉴权：GatewayAccessUseCase；Bearer / x-api-key
│   ├── openai_compat_router.py # /v1/chat/completions 等 OpenAI 形
│   ├── anthropic_compat_router.py  # POST /v1/messages Anthropic 形
│   └── gateway_proxy_context.py    # 对外代理共用 ProxyContext 构造
├── application/
│   ├── gateway_access_use_case.py   # Bearer vkey、代理团队解析、vkey touch；成员角色经 MembershipPort
│   ├── ports.py                     # GatewayProxyProtocol、GatewayCallContext（跨域依赖倒置）
│   ├── gateway_proxy_factory.py     # get_gateway_proxy() → GatewayBridge 单例
│   ├── internal_bridge_actor.py     # resolve_internal_gateway_user_id / team_id
│   ├── bridge_attribution.py        # GatewayBridgeAttribution（内部桥接计费工作区）
│   ├── litellm_bridge_payload.py    # LiteLLM kwargs → 桥接参数拆分
│   ├── internal_bridge.py           # GatewayBridge 实现
│   ├── anthropic_openai_bridge.py   # Anthropic ↔ OpenAI 形 JSON（对外 /v1/messages）
│   ├── management/                # 管理面读写分包（与 CQRS 读/写侧对应）
│   │   ├── reads.py               # GatewayManagementReadService
│   │   ├── writes.py              # GatewayManagementWriteService
│   │   └── usage_reads.py         # GatewayUsageReadService（兼容用量 API）
│   ├── proxy_use_case.py          # 对外 LLM 代理编排（OpenAI 与 Anthropic 经 chat 共用）
│   └── jobs.py                    # 后台循环；rollup SQL 在 infrastructure 仓储
├── domain/                       # 类型、虚拟 Key 算法、领域错误、ManagementTeamContext
└── infrastructure/             # ORM、仓储、Router 单例、回调、护栏
    └── models/__init__.py        # 再导出 Team / TeamMember（与 Alembic 聚合 import），权威定义在 tenancy

domains/gateway/domain/usage_read_model.py  # UsageAggregation（管理面日志/大盘读模型）
domains/agent/infrastructure/llm/gateway.py   # LLMGateway
```

**依赖方向**

- `presentation → application（UseCase + 管理面 management 读写服务）→ domain`
- `infrastructure` 由 application 经仓储调用；**禁止** domain 依赖 infrastructure。
- **团队与成员**：`domains.gateway.application` 使用 `domains.tenancy` 的 `TeamService` / `TeamRepository` 与 `Team` ORM；**成员角色**经 `libs.iam.tenancy.MembershipPort`（默认 `TenancyMembershipAdapter`），**禁止**在 Gateway 应用层直接使用 `TeamMemberRepository`。`gateway.infrastructure.models` 仅再导出 `Team` / `TeamMember` 供 Alembic 聚合 import。团队管理 HTTP 在 `domains.tenancy.presentation.teams_router`（仅依赖 `TeamService` 与 identity 依赖，**不**引用 `domains.gateway.application`）。
- **可映射 HTTP 的领域错误**：`TeamNotFoundError`、`TeamPermissionDeniedError`、`PersonalTeamNotInitializedError` 与基类 `HttpMappableDomainError` 定义在 **`libs.exceptions`**；`libs/iam/team_http.map_team_access_exception_to_http` 负责上述团队错误的 HTTP 映射。`GatewayError` 继承 `HttpMappableDomainError`；`gateway.presentation.http_error_map` 先委托团队映射再处理其余 Gateway 异常。`tenancy.presentation.team_dependencies` **不**依赖 `domains.gateway.presentation`。

**CQRS（管理面）**

- `/api/v1/gateway/*` 的 **读** → `GatewayManagementReadService`；**写** → `GatewayManagementWriteService`。路由与 `deps` 不 `new *Repository`。

**UseCase 与 CQRS**

- **UseCase**：按场景端到端（如 `ProxyUseCase`、`GatewayAccessUseCase`），可多次读、少量写。
- **CQRS 拆分**：适合管理面 CRUD 大、读写易分叉；鉴权 + `touch` 收拢为 `GatewayAccessUseCase`，不为单行写单独建 Command 文件。

**术语对照（Query / Command 与业务命名）**

| 工程/CQRS 惯用名 | 类名（业务语感） | 说明 |
|------------------|------------------|------|
| Query 侧（只读） | `GatewayManagementReadService` | 管理 API 列表/详情/聚合读模型 |
| Command 侧（变更） | `GatewayManagementWriteService` | 管理 API 创建/更新/删除 |
| 用量只读（兼容层） | `GatewayUsageReadService` | Identity `/usage/*` 等，不暴露 Gateway ORM |

实现分包目录为 `application/management/`（`reads.py` / `writes.py` / `usage_reads.py`），与「Query/Command」一一对应，便于团队沟通时口头用「管理读服务 / 管理写服务」指代两侧。

**后台任务**：`jobs.py` 调度；rollup 实现在 `infrastructure/repositories/metrics_rollup_repository.py`。

---

## 3. 运行时拓扑（简化）

```mermaid
flowchart TB
  subgraph clients [Clients]
    UI[Web /gateway]
    Ext[OpenAI / Anthropic SDK -> /v1]
    Agent[Agent LLMGateway]
  end
  subgraph gateway_http [FastAPI Gateway]
    Mgmt["/api/v1/gateway/*"]
    V1["/v1/* OpenAI + Anthropic"]
  end
  subgraph core [Core]
    Router[LiteLLM Router Singleton]
    Budget[BudgetService / Redis]
    Access[GatewayAccessUseCase]
    ReadSvc[GatewayManagementReadService]
    WriteSvc[GatewayManagementWriteService]
  end
  UI --> Mgmt
  Ext --> V1
  Agent -->|internal_proxy| Bridge[GatewayBridge]
  Bridge --> ProxyUC[ProxyUseCase进程内]
  ProxyUC --> Router
  Mgmt --> Access & ReadSvc & WriteSvc
  V1 --> Access
  V1 --> Router
  Router --> Budget
  Router --> LogRepo[RequestLogRepository]
```

说明：**`GatewayBridge` 不经过 HTTP 再打 `/v1`**，而是在同一进程内 `AsyncSession` 上直接调用 `ProxyUseCase`，与 OpenAI 兼容路由共享同一套代理与计量逻辑；上图单独画出 `V1` 表示外部客户端入口，与内部桥并列。

### 3.1 本地开发与运行模式

| 模式 | 依赖 | `gateway_internal_proxy_enabled` | 行为 |
|------|------|-----------------------------------|------|
| **完整 Gateway（对齐生产）** | 已执行 gateway 相关 DB 迁移；Redis 可用（Router 冷却/共享）；请求内能解析归因 `user_id` **或** 配置了委派 UUID | `True`（默认） | `LLMGateway` / `EmbeddingService`（API）优先经 `GatewayBridge` → `ProxyUseCase`，写入请求日志与预算链路。 |
| **轻量直连（刻意降级）** | 可无 Redis / 未迁库；仅验证 Agent 逻辑 | `False` | 直连 LiteLLM，**不**走 Gateway 观测闭环；与生产口径不同，勿误以为本地通过即线上管控完备。 |

**纯本地向量（FastEmbed）**：不经 Gateway，无供应商 API，属刻意设计。

**无注册用户上下文**：若未配置 `gateway_internal_proxy_delegate_user_id`，内部桥无法归因，将回退直连（除非 `gateway_internal_proxy_fail_closed=True`，此时桥接失败会抛错而非静默回退）。

**推荐**：CI 或合并前至少保留一条「开桥 + 已解析 user_id 或委派 ID」的集成路径，避免生产专用代码腐烂。

---

## 4. 认证与团队上下文

| 入口 | 鉴权 | 团队 |
|------|------|------|
| `/v1/*` | `sk-gw-*` 或 `sk-*` + `gateway:proxy`；**`Authorization: Bearer`** 或 **`x-api-key`**（Bearer 优先） | `X-Team-Id` 可选；缺省 personal team |
| `/api/v1/gateway/*` | JWT（`RequiredAuthUser`），匿名 **401** | `X-Team-Id` 优先，否则 personal team（`TenancyManagementTeamResolveUseCase` + `MembershipPort`） |

RBAC 与 `libs/db/permission_context.py`：`deps.py` 调用 **`GatewayAccessUseCase`**。

### 4.1 域划分、术语与用量读模型（`UsageAggregation`）

| 域 / 层 | 职责 | 与本节相关类型 |
|---------|------|----------------|
| **Tenancy** | `Team`（`kind=personal|shared`）、成员、`ManagementTeamContext`；**personal team 仍是 `Team` 表的一行**，用户通过成员关系属于该工作区。 | `Team.id` 可作为当前工作区 ID。 |
| **Gateway 管理读** | 请求日志列表/详情/大盘摘要的**切片维度**；**不**改变 Tenancy 实体。 | `UsageAggregation`（`domains/gateway/domain/usage_read_model.py`）。 |
| **Identity** | JWT 主体 `user_id`。 | 与 `usage_aggregation=user` 聚合键一致。 |
| **Gateway 应用（内部桥接）** | `GatewayCallContext`、`GatewayBridgeAttribution`：内部桥接的 **Actor** 与 **计费工作区**（日志 `team_id`）。 | 与 HTTP `usage_aggregation` **正交**（桥接不携带该查询参数）。 |

**`usage_aggregation`（查询参数，默认 `workspace`）**

| 取值 | 含义 |
|------|------|
| `workspace` | 按 **`X-Team-Id` → CurrentTeam.team_id`** 过滤/聚合；该 ID 可为 **personal** 或 **shared** 工作区。 |
| `user` | 按当前登录 **`user_id`** 跨工作区聚合/过滤（与日志行 `user_id` 对齐）；**不**表示「无团队用户」。 |

**与预算 `BudgetUpsert.scope`（`system|team|key|user`）正交**：后者表示预算作用域类型，禁止与 `UsageAggregation` 混用同一组字面量。

**破坏性变更（已无兼容）**：`GET /logs`、`GET /logs/{log_id}`、`GET /dashboard/summary` **已移除**查询参数 `scope=team|personal`，客户端必须改用 **`usage_aggregation=workspace|user`**。

### 4.2 仪表盘与明细日志的数据源

- **`GET /dashboard/summary`**：聚合自 **`gateway_request_logs`**（PostgreSQL），受成功请求采样配置 `gateway_request_log_success_sample_rate` 影响（见 `domains/gateway/infrastructure/gateway_log_sampling.py` 与 `custom_logger` 注释）。
- **Redis 计数**（`gateway:metrics:*`）：CustomLogger 中可与 DB 写入路径不同步；**管理面大盘以 DB 为准**。
- **凭据归因**：`gateway_request_logs` 含可空列 **`credential_id`**、**`credential_name_snapshot`**；`GET /api/v1/gateway/logs` 支持查询参数 **`credential_id`** 过滤；LiteLLM Router deployment 的 **`model_info`** 写入 `gateway_credential_id` / `gateway_credential_name` / `gateway_credential_scope`，与 `ProxyUseCase._build_metadata` 注入的 `gateway_*` 字段互为补充；**`gateway_metrics_hourly`** rollup 唯一维度含 **`credential_id`**（与历史 NULL 行兼容）。

#### 注册模型 deployment 归因（与 `route_name` 正交）

- **`route_name`**：客户端请求体中的 **`model`** 字符串（可为路由 **虚拟名**）；用于直连或历史未写 deployment 列的聚合。
- **`deployment_gateway_model_id` / `deployment_model_name`**：来自 Router deployment **`model_info.id`**（即 `GatewayModel.id`）与 **`gateway_model_name`**（注册别名）；经路由命中某条 **注册模型** 时写入，使「虚拟名进线」仍可按 **注册行** 汇总用量。
- **管理面 `GET /models/usage-summary`**：`GatewayManagementReadService` 将 **按 deployment id 聚合** 与 **仅 `deployment_gateway_model_id` 为空时按 `route_name` 聚合** 两段结果 **相加**（避免双计数）。
- **`gateway_route_snapshot`**：`ProxyUseCase._build_metadata` 在命中 `GatewayRoute` 时写入 `virtual_model` / `primary_models` / `strategy`；读路径带 **60s 模块级 TTL 缓存**（`application/route_snapshot_cache.py`），降低热路径重复查库。

### 4.3 入站「Gateway 调用凭据」与出站「上游凭据」（术语与域划分）

| 概念 | 含义 | 存储 / 生命周期 |
|------|------|-----------------|
| **入站 · 虚拟 Key（vkey）** | 客户端调用 **`/v1/*`** 的 Bearer / `x-api-key`，前缀 **`sk-gw-*`**；团队绑定、模型白名单、RPM/TPM、key 级预算与网关日志策略以 **Gateway** 表为准。 | `gateway_virtual_keys` |
| **入站 · 平台 API Key** | 同一 **`/v1/*`** 入口支持 Identity 签发的 **`sk-*`**，且 scope 含 **`gateway:proxy`**；团队由 **`X-Team-Id`**（可选，缺省 personal team）解析。与 vkey **不合并为一张表**：吊销、scope、多能力复用由 **Identity** 负责；默认网关策略与 vkey 路径不对等处应在产品文档中显式说明。 | Identity API Key |
| **出站 · Provider 凭据** | LiteLLM 向上游（OpenAI、Anthropic 等）发起请求时使用的 Key/Base，即 **`provider_credentials`**（system / team / user scope）。 | Gateway 凭据池 |

**产品表述建议**：将前两者统称为「**调用本平台的 Gateway 令牌**」两种形态；与设置页「大模型 / 上游 API Key」严格区分，避免用户把 `sk-gw-*` 与 OpenAI `sk-*` 混用。

### 4.4 平台 API Key 与 vkey 管控「完全对齐」（方向 C）评估结论

**默认不实施**：在 Identity 与 Gateway 各维护一套与 `GatewayVirtualKey` 同字段的白名单、限流与日志开关，会造成**双真源**、迁移与 UI 同步成本高，且与「平台 Key 多 scope 复用」的定位冲突。

**若未来强需求**（合规或商业化要求「一把 `sk-*` 也必须 per-key 配额」）：优先在应用层引入共享的 **`InboundPolicy`** 值对象（或单一 JSON 策略 blob）由 **一处** 配置驱动两种入站实现，而不是复制两套管理界面；并评估请求日志是否需新增 `platform_api_key_id` 列（当前可先经 LiteLLM metadata 中的 `gateway_platform_api_key_id` 归因）。

### 4.5 模型注册：主调用面（`capability`）与特性（`tags` / `model_types`）

| 概念 | 含义 | 典型存储 |
|------|------|----------|
| **主调用面** | 该 **注册别名** 默认对应的 OpenAI 兼容 HTTP 族：`POST /v1/chat/completions`、`/v1/images/generations`、`/v1/videos`、`/v1/moderations` 等 | ``GatewayModel.capability``（单列）；与 ``GatewayCapability`` 枚举一致 |
| **特性 / 产品能力** | 是否视觉、工具、生图、视频生成标记等；用于选择器、Agent 参数与 UI 芯片 | ``GatewayModel.tags``（JSONB）；管理 API 派生 ``model_types``、``selector_capabilities``（与 ``ModelCapabilitySnapshot`` 对齐） |

**约束**：``uq_gateway_models_team_name`` 决定同一 ``(team_id, name)`` 仅一行注册记录，因而 **一个别名只有一个主调用面**。若同一逻辑产品既要走 chat 又要走 images/videos 等不同 HTTP 面，应使用 **不同注册别名**（例如 `my-model` 与 `my-model-image`），并在 ``GatewayRoute.primary_models`` 中指向对应注册名。

### 4.6 LiteLLM Router 与「同别名多调用面」

LiteLLM Router 的 ``model_list`` 以 **deployment 的 ``model_name``** 参与调度；同一字符串多 deployment 时行为依赖版本与具体调用函数（``acompletion`` / ``aimage_generation`` / ``avideo_generation`` 等），**不应依赖未文档化的隐式过滤**。

**工程定案（当前阶段）**：需要多 HTTP 面时采用 **别名拆分**（多行 ``GatewayModel``、不同 ``name``），而非在同一 ``name`` 上叠多个主调用面。若未来要强需求「单展示名多面」，需单独做 LiteLLM 行为验证与 Router 构建改造后再定 schema。

---

## 5. 数据与持久化要点

- **分区表**：`gateway_request_logs` 为分区表；主键 **`(id, created_at)`**。禁止仅用 `session.get(Log, id)`，见 `RequestLogRepository.get_for_team`。
- **凭据**：`provider_credentials` 加密；Router 构建时解密参与 `model_list`。
- **迁移**：`alembic/versions/`。

---

## 6. 软件工程实践

### 6.1 测试

| 层级 | 路径 | 关注点 |
|------|------|--------|
| 单元 | `tests/unit/gateway/` | Personal team、vkey、PII、仓储 |
| 集成 | `tests/integration/api/test_gateway_management_api.py` | JWT、`GET /teams`、`X-Team-Id` |

```bash
uv run pytest tests/unit/gateway/ tests/integration/api/test_gateway_management_api.py -q
```

### 6.2 配置（与 `bootstrap/config.py` 字段一致）

环境变量由 Pydantic Settings 推导（通常为 **大写 + 下划线**，例如 `GATEWAY_INTERNAL_PROXY_ENABLED`），以下列出 **Settings 属性名**：

- `gateway_internal_proxy_enabled`：内部 Chat/Embedding（API）是否优先走 `GatewayBridge`。
- `gateway_internal_proxy_fail_closed`：桥接异常时是否**禁止**静默回退直连（`True` 则抛出）。
- `gateway_internal_proxy_delegate_user_id`：无 `PermissionContext.user_id` 时用于 Gateway 归因的委派 UUID（后台任务、worker 等）。
- `gateway_router_redis_url`：Router 跨进程状态；缺省可复用全局 `redis_url`。

### 6.3 前后端契约

- `frontend/src/api/gateway.ts`：日志/大盘使用查询参数 **`usage_aggregation`**（`workspace` | `user`），与后端 `UsageAggregation` 对齐；与 `schemas/common.py` 响应体对齐。
- `frontend/src/stores/gateway-team.ts` → 请求头 **`X-Team-Id`**。
- `frontend/src/pages/settings/index.tsx`：支持查询参数 **`?tab=api`**（及 `credentials`、`mcp` 等）深链到对应设置子页，便于 Gateway 控制台与「API 密钥」说明互链。
- `frontend/src/types/api-key.ts`：`ApiKeyScope` 与后端 **`gateway:proxy` / `gateway:admin` / `gateway:read`** 对齐；创建 Key 时可勾选 Gateway 相关作用域。

### 6.4 已知风险

| 项 | 说明 |
|----|------|
| Router 单例 | 多 worker 依赖 Redis 一致性；改模型后需 `reload_router` 可达。 |
| 测试覆盖 | 预算/限流/流式等以单元与手工为主，可补集成。 |
| Pydantic V2 | MCP 相关 `Config` 弃用警告与 Gateway 无关，可择机 `ConfigDict`。 |

---

## 7. 前端控制台索引

| 区域 | 路径 |
|------|------|
| 页面 | `frontend/src/pages/gateway/` |
| API | `frontend/src/api/gateway.ts` |
| 团队 | `frontend/src/stores/gateway-team.ts`、`components/layout/team-switcher.tsx` |
| 权限 | `frontend/src/hooks/use-gateway-permission.ts` |

---

## 8. 相关文档

- [LLM_GATEWAY_ARCHITECTURE.md](./LLM_GATEWAY_ARCHITECTURE.md)
- [GATEWAY_COMPATIBILITY_CHECK.md](./GATEWAY_COMPATIBILITY_CHECK.md)
- [PERMISSION_SYSTEM_ARCHITECTURE.md](./PERMISSION_SYSTEM_ARCHITECTURE.md)
