# 跨团队聚合虚拟 Key（multi-tenant vkey）实施方案

> **实现状态（2026-06）**：已合并至主分支开发线（`gateway_virtual_key_team_grants`、管理 API、前缀派发、前端 grants 抽屉、生命周期 revoke）。权威架构文档：[backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md §4.4.1](../../backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md)。

## Context

**业务痛点**：用户加入多个 team，不同 team 有不同模型；当前一把 `sk-gw-*` 硬绑定单一 team，跨 team 调用必须切换 vkey，第三方 SDK（IDE/CLI/SaaS）几乎无法做到。

**目标**：一把 `sk-gw-*` 同时访问用户所属多个 team 的模型；客户端通过 `model` 字段前缀 `team-slug/model-name` 隐式派发；调用归属（审计/预算/metrics）落到**实际命中的 team**。

**用户已确认的 5 条决策（必须严格遵守）**：
1. 团队选择**仅**通过 `model` 前缀 `team-slug/...`（不改 X-Team-Id 头契约、不引入 URL 路径式入口）
2. grants 表只保留 `(vkey_id, tenant_id)` 最简形态；模型/能力白名单沿用 vkey 全局字段
3. team owner/admin **不能**撤销外来 grant；仅 vkey 创建者本人可撤销
4. 用户被踢出 team 后**仅靠离线任务清理**；调用热路径不做 membership 实时校验
5. `request_log.tenant_id` / 预算 / metrics 写入**实际命中 team**

**事实校准**：`gateway_virtual_keys` 表实际列名是 `tenant_id`（继承 [TenantScopedMixin](file:///e:/project/ai-agent/backend/libs/orm/base.py)），下文一律以 `tenant_id` 表达 vkey 主属 team。

**授权模型是显式 Opt-In（严格逐个授权，不是自动全集合）**：
- 主属 team 自动写一行 `is_self=TRUE` 自洽 grant（保证旧行为 100% 向后兼容）
- **其他 team 不会自动进入 grants**；vkey 创建者必须主动调 `POST /api/v1/gateway/teams/{team_id}/keys/{vkey_id}/grants` 逐个选择要聚合哪些 team（可多选，一次请求一批）
- 可限选集合 = 该用户当前 membership ∖ 已授权 ∖ 主属（`GET /grantable-teams` 返回）
- 逐个撤销：`DELETE /grants/{tenant_id}`；UI 为多选 picker + 项级“移除”按钮
- 这意味着：“所属 5 个 team”不等于“一把 vkey 能跨 5 个 team调用”；用户完全掌控在哪些 team 上启用这把 vkey。

**权限不变不式**：不论授权多少个 team，vkey 本身仍仅 `created_by_user_id` 本人可见/可撤销；team owner/admin 看不到外来 grant（完全保护创建者隐私，遵守决策 #3）。

---

## Task 1 — 数据库与迁移

**新表** `gateway_virtual_key_team_grants`（无 DB FK，与既有 `gateway_*` 表约定一致）：

| 列 | 类型 | 说明 |
|---|---|---|
| id | uuid pk |  |
| vkey_id | uuid not null index | 引用 `gateway_virtual_keys.id` |
| tenant_id | uuid not null index | 被授权 team |
| is_active | bool not null default true | 软撤销标记 |
| granted_by_user_id | uuid not null index | = vkey.created_by_user_id（守恒） |
| is_self | bool not null default false | 自洽 grant（vkey 主属 team），离线清理跳过 |
| revoked_at / revoked_reason | timestamptz / varchar(40) | `'owner_revoked' \| 'membership_lost' \| 'team_archived'` |
| created_at / updated_at | timestamptz |  |

**索引**：
- `UNIQUE(vkey_id, tenant_id) WHERE is_active=TRUE` — 防重复 active grant
- `INDEX(vkey_id) WHERE is_active=TRUE` — 鉴权热路径查 grants
- `INDEX(granted_by_user_id, tenant_id) WHERE is_active=TRUE` — 离线清理反查

**回填**：迁移内为所有现存 vkey 写一行自洽 grant `(vkey_id, vkey.tenant_id, is_self=TRUE)`；先回填后建 unique 索引（参考 [20260513_unique_system_vkey_per_team.py](file:///e:/project/ai-agent/backend/alembic/versions/20260513_unique_system_vkey_per_team.py) 风格）。`created_by_user_id IS NULL` 的 system vkey 用 sentinel UUID 回填，但 application 层禁止 system vkey 操作 grants。

**关键文件**：
- [backend/alembic/versions/20260605_vkey_team_grants.py](file:///e:/project/ai-agent/backend/alembic/versions/) （新增；`down_revision` 接当前 head，实施前先 `alembic heads` 确认）
- [backend/domains/gateway/infrastructure/models/virtual_key_team_grant.py](file:///e:/project/ai-agent/backend/domains/gateway/infrastructure/models/) （新增；不继承 `TenantScopedMixin`，仅含 tenant_id 字段）
- [backend/domains/gateway/infrastructure/repositories/virtual_key_team_grant_repository.py](file:///e:/project/ai-agent/backend/domains/gateway/infrastructure/repositories/) （新增；`upsert_active` 用 `INSERT ... ON CONFLICT DO NOTHING`）

---

## Task 2 — 鉴权链路接入 grants

**关键架构决定**：**前缀解析必须在 proxy 路由层（拿到 body 之后），不能在 [bearer_vkey_or_apikey_auth](file:///e:/project/ai-agent/backend/domains/gateway/presentation/deps.py#L215) dependency 内**——FastAPI dep 阶段尚未反序列化 body。

**鉴权阶段只做：**
1. [VirtualKeyPrincipal](file:///e:/project/ai-agent/backend/domains/gateway/domain/types.py) 增字段：`granted_team_ids: tuple[uuid.UUID, ...]`
2. [_gateway_principal_from_vkey_plain](file:///e:/project/ai-agent/backend/domains/gateway/presentation/deps.py#L100-L160) 在拉完 `team_role` 与 `permission_ctx` 之间**顺序 await** 一次 `access.list_active_grant_tenant_ids(vkey_id)`（SQLAlchemy AsyncSession 不支持并发 await）
3. [GatewayAccessUseCase](file:///e:/project/ai-agent/backend/domains/gateway/application/gateway_access_use_case.py) 暴露 `list_active_grant_tenant_ids(vkey_id)`，背后调 [virtual_key_team_grant_reads](file:///e:/project/ai-agent/backend/domains/gateway/application/management/) 中的 `list_active_grant_tenant_ids(session, vkey_id)`

**X-Team-Id 头放宽**（保留 [GatewayVkeyTeamHeaderMismatchError](file:///e:/project/ai-agent/backend/domains/gateway/domain/errors.py#L43)，仅放宽校验）：
- [assert_vkey_team_header_compatible](file:///e:/project/ai-agent/backend/domains/gateway/domain/virtual_key_access.py#L83) 改签名为 `(bound_team_id, granted_team_ids, x_team_id)`：header 在 `{bound} ∪ granted` 集合内即放行
- 错误文案改为 "X-Team-Id must be vkey's bound team or a granted team"

---

## Task 3 — model 前缀派发（应用层纯函数）

**新模块** [backend/domains/gateway/application/vkey_team_resolution.py](file:///e:/project/ai-agent/backend/domains/gateway/application/) ：

```python
@dataclass(frozen=True, slots=True)
class VkeyModelDispatch:
    effective_team_id: uuid.UUID
    real_model_name: str       # 派发后的 model（去掉 team prefix）
    matched_slug: str | None   # None 表示落主属 team

async def dispatch_vkey_model(
    session, *, vkey: VirtualKeyPrincipal, raw_model: str
) -> VkeyModelDispatch
```

**派发算法**（严格按此实现，避免与 `vendor/model` 命名冲突）：
1. `vkey.is_system` → 直接返回 `(vkey.tenant_id, raw_model, None)`，跳过 prefix
2. `raw_model` 不含 `/` → 同上
3. 切首个 `/` 得 `slug_candidate, rest`
4. 查 `TeamRepository.list_by_ids_with_slug(vkey.granted_team_ids)` 拿 `{slug → tenant_id}` 映射（**仅限 grants 集合内，不全表扫**）
5. slug 命中 → 返回 `(matched_tenant_id, rest, slug_candidate)`
6. 未命中 → 返回 `(vkey.tenant_id, raw_model, None)`，让 `openai/gpt-4o` 等 vendor 前缀走主属 team 解析

**Reserved slug 防御**：在 [team_service.py](file:///e:/project/ai-agent/backend/domains/tenancy/application/team_service.py) 创建/重命名时拒绝保留字（=主流 LiteLLM provider 名集合，硬编码 + 单测固定），避免 team slug 与 vendor 同名造成派发歧义。

**Strict 模式开关**（默认关闭）：`settings.gateway_vkey_strict_team_prefix=True` 时，`<a>/<b>` 含未命中 slug → 抛 `VkeyTeamPrefixUnknownError(400)`（避免静默落主属）。生产先关，运营再决定开。

---

## Task 4 — Proxy 热路径接线（核心收益：业务管线零侵入）

**dispatch 落点**：在 router 层**拿到 body 之后**调用 `dispatch_vkey_model`，重写 `proxy_body["model"]` 为 `dispatch.real_model_name`，并把 `dispatch.effective_team_id` 透传进 [ProxyContext.team_id](file:///e:/project/ai-agent/backend/domains/gateway/application/proxy_context.py)。

**改造点（最小集合）**：
- [backend/domains/gateway/presentation/openai_compat_router.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/) 的 chat/completions/embeddings 等所有 vkey 入口
- [backend/domains/gateway/presentation/anthropic_compat_router.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/) 同步
- [backend/domains/gateway/presentation/proxy_request_context.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/) `proxy_context_from_request` 接受可选 `dispatch`
- [backend/domains/gateway/presentation/gateway_proxy_context.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/) 新增 `proxy_context_with_dispatch(...)` 工厂
- [ProxyContext](file:///e:/project/ai-agent/backend/domains/gateway/application/proxy_context.py) 加字段 `client_raw_model: str | None` —— 保留派发前的原始 model 名，写到日志 `gateway_route_name`

**业务管线零侵入**：[proxy_litellm_client.py](file:///e:/project/ai-agent/backend/domains/gateway/application/proxy_litellm_client.py) / [proxy_metadata_builder.py](file:///e:/project/ai-agent/backend/domains/gateway/application/) / [proxy_response_adapter.py](file:///e:/project/ai-agent/backend/domains/gateway/application/) / [proxy_guard.py](file:///e:/project/ai-agent/backend/domains/gateway/application/) 现有所有 `ctx.team_id` 调用点**全部不动**——dispatch 已让 ctx.team_id == effective_team_id，审计/预算/限流自然落对位置。

**关闭跨 grants 隐式 fallback**：[_resolve_personal_team_model](file:///e:/project/ai-agent/backend/domains/gateway/application/model_or_route_resolution.py#L180) 与 multi-tenant 显式派发的语义重叠。改造 [_resolve_model_or_route_uncached](file:///e:/project/ai-agent/backend/domains/gateway/application/model_or_route_resolution.py#L196) 增 `enable_personal_fallback: bool` 参数；调用方按 `len(vkey.granted_team_ids) <= 1` 自动决定，向后兼容（仅自洽 grant 时保留旧 fallback）。

**缓存零改动**：[resolve_model_cache](file:///e:/project/ai-agent/backend/domains/gateway/application/resolve_model_cache.py) 的 key `(team_id, name, user_id)` 含 effective_team_id 后天然分桶。

**审计标记增强**（[proxy_metadata_builder.py](file:///e:/project/ai-agent/backend/domains/gateway/application/) `_merge_user_and_model_metadata`）：
- `gateway_route_name = ctx.client_raw_model or virtual_model`
- `gateway_dispatched_via_prefix: bool`
- `gateway_vkey_owner_team_id = vkey.team_id`（vkey 主属，做"跨 team 流量分析"用）

---

## Task 5 — 管理 API（vkey owner 自助）

**Endpoints**（鉴权复用 [RequiredTeamMember](file:///e:/project/ai-agent/backend/domains/gateway/presentation/deps.py)，业务 actor 校验由 [assert_virtual_key_accessible_by_actor](file:///e:/project/ai-agent/backend/domains/gateway/domain/virtual_key_access.py#L48) 把关）：

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/gateway/teams/{team_id}/keys/{key_id}/grants` | 列 active grants（含自洽行） |
| POST | `/api/v1/gateway/teams/{team_id}/keys/{key_id}/grants` | body: `{tenant_ids: [uuid]}` 幂等批量授权 |
| DELETE | `/api/v1/gateway/teams/{team_id}/keys/{key_id}/grants/{tenant_id}` | 撤销；is_self → 422 |
| GET | `/api/v1/gateway/keys/{key_id}/grants/grantable-teams` | 列出当前用户可作目标的 team |

**权限规则**：
- 仅 `vkey.created_by_user_id == actor` 可访问（其它一律 404，包括 team owner）
- system vkey → 403 [SystemVirtualKeyForbiddenError](file:///e:/project/ai-agent/backend/domains/gateway/domain/errors.py#L105)
- POST 目标 tenant_id 必须 ∈ [list_team_ids_for_user(actor)](file:///e:/project/ai-agent/backend/domains/tenancy/application/team_membership_queries.py)，否则 422 `gateway/grant_target_not_member`
- 主属 team（`tenant_id == vkey.tenant_id`）的 POST 直接幂等忽略
- DELETE `is_self=TRUE` → 422 `gateway/grant_self_not_revocable`

**新增文件**：
- [backend/domains/gateway/application/management/virtual_key_team_grant_reads.py](file:///e:/project/ai-agent/backend/domains/gateway/application/management/) — `list_active_grants_for_vkey` / `list_active_grant_tenant_ids` / `list_grantable_teams_for_actor`
- [backend/domains/gateway/application/management/virtual_key_team_grant_writes.py](file:///e:/project/ai-agent/backend/domains/gateway/application/management/) — `grant_vkey_to_teams` / `revoke_vkey_team_grant` / `revoke_grants_for_user_team_membership`（离线任务复用）
- [backend/domains/gateway/presentation/schemas/grants.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/schemas/) — `VirtualKeyTeamGrant` / `VirtualKeyGrantBatchRequest` / `GrantableTeam`
- [backend/domains/gateway/presentation/routers/virtual_key_grants.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/routers/)
- 既有 [vkey_to_response](file:///e:/project/ai-agent/backend/domains/gateway/presentation/routers/_common.py) / [virtual_key_from_orm](file:///e:/project/ai-agent/backend/domains/gateway/application/management/virtual_key_read_mappers.py) 扩展支持 `granted_team_ids: tuple[UUID, ...]`，调用方批量预取避免 N+1（参考 [list_with_quotas_for_vkeys](file:///e:/project/ai-agent/backend/domains/gateway/application/management/managed_team_virtual_key_reads.py) 风格）

---

## Task 6 — 离线清理任务

**实现形态**：cron 触发的独立脚本（与项目既有 [scripts/reset_quota.py](file:///e:/project/ai-agent/backend/scripts/) 约定一致；不引 celery / in-process scheduler）。

**新文件** [backend/scripts/cleanup_stale_vkey_grants.py](file:///e:/project/ai-agent/backend/scripts/) ，核心 SQL：

```sql
UPDATE gateway_virtual_key_team_grants g
   SET is_active=FALSE, revoked_at=now(),
       revoked_reason='membership_lost', updated_at=now()
 WHERE g.is_active=TRUE AND g.is_self=FALSE
   AND NOT EXISTS (
     SELECT 1 FROM gateway_team_members tm
      WHERE tm.user_id=g.granted_by_user_id AND tm.team_id=g.tenant_id
   );
```

集合幂等；多 worker 并发跑只会产生重复 update 不会双撤销。建议 cron `*/5 * * * *`。

**同步触发缩窗**（用户决策 #4 接受窗口期，此为合理增强）：[team_service.remove_member](file:///e:/project/ai-agent/backend/domains/tenancy/application/team_service.py) 成功后 fire-and-forget [register_app_background_task](file:///e:/project/ai-agent/backend/libs/background_tasks.py) 调 `revoke_grants_for_user_team_membership(user_id, tenant_id)`。**热路径仍不查 membership**，符合决策。

---

## Task 7 — 前端

**类型扩展** [frontend/src/api/gateway/keys.ts](file:///e:/project/ai-agent/frontend/src/api/gateway/keys.ts)：
```ts
interface VirtualKey { ... granted_team_ids: string[] }  // 含主属，min length 1
interface VirtualKeyTeamGrant { id; vkey_id; tenant_id; is_self; created_at; revoked_at; granted_team_name; granted_team_slug }
interface GrantableTeam { team_id; name; slug; role }
```

**API 方法**新增 `listGrants` / `grantToTeams` / `revokeGrant` / `listGrantableTeams`。

**列表页** [frontend/src/features/gateway-keys/](file:///e:/project/ai-agent/frontend/src/features/gateway-keys/)：
- 每行新增"跨 team 派发"列：`granted_team_ids.length > 1` 显示 Badge + 抽屉入口；否则 `—`
- 新组件目录 `frontend/src/features/gateway-keys/grants/`：
  - `key-grants-drawer.tsx`（Tabs：已授权 / 可授权；**多选复选框 + Apply**）
  - `use-vkey-grants.ts` / `use-grantable-teams.ts`（React Query）
  - `use-team-slug-map.ts`（slug 映射，与 reveal hint 共用）

**抽屉交互明细（按需选择要聚合哪些 team）**：
- 默认全部未勾选（遵守"默认不聚合"原则）
- 可授权列表仅含该用户当前 membership 中除主属 team 之外的 team；带 search/filter（如果超 10 个）
- 贴心提示：项后缀显示该 team 已注册的模型数（如 "team-data · 12 models"）帮助用户判断是否要勾选
- "全选 / 反选"为可选便捷提供，不默认全选；**避免误导为"勾一下就可以跨所有 team"**
- Apply 后调 `POST .../grants` body `{tenant_ids: [勾选 ids]}` 幂等（允许重复 apply 同批）
- 已授权 Tab 中，项级“移除”按钮 → `DELETE .../grants/{tenant_id}`；主属 team 标黄锁定图标不可移除

**reveal 弹窗** [virtual-key-reveal-dialog.tsx](file:///e:/project/ai-agent/frontend/src/features/gateway-keys/virtual-key-reveal-dialog.tsx) 增折叠 hint：展示已授权 team 列表 + `model: "<slug>/<name>"` 调用示例 + cURL 片段。

**`/managed-team-keys` 视图**：[managed_team_virtual_key_reads](file:///e:/project/ai-agent/backend/domains/gateway/application/management/managed_team_virtual_key_reads.py) 返回的 `VirtualKeyReadModel` 同步带 `granted_team_ids`，前端 [keys-workspace.tsx](file:///e:/project/ai-agent/frontend/src/features/gateway-keys/) 通过 [useVisibleGatewayKeys](file:///e:/project/ai-agent/frontend/src/features/gateway-keys/) 自动获益，无需新分支。

---

## Task 7.5 — 同名模型在多 team 的语义（专项澄清）

**底层事实**：[gateway_models](file:///e:/project/ai-agent/backend/domains/gateway/infrastructure/models/gateway_model.py#L102) 表有 `UniqueConstraint("tenant_id", "name")`，team-X 的 `gpt-4o` 与 team-Y 的 `gpt-4o` 在 DB 层是**两条独立记录**，各自绑定不同凭据/路由/定价/限流。同名模型本身**不存在跨 team 冲突**。

**用户视角语义（在本方案下严格定义）**：

| 客户端发送 | vkey 主属=X、grants={X,Y} 时落点 |
|---|---|
| `model="gpt-4o"`（无前缀） | **必落主属 team-X 的 `gpt-4o`**；team-X 没有则 422 [GatewayModelNotFoundError](file:///e:/project/ai-agent/backend/domains/gateway/domain/errors.py#L173)，**不**透明 fallback 到 team-Y |
| `model="team-x-slug/gpt-4o"` | 显式落 team-X 的 `gpt-4o` |
| `model="team-y-slug/gpt-4o"` | 显式落 team-Y 的 `gpt-4o` |
| `model="team-z-slug/gpt-4o"`（z 不在 grants） | slug 未命中 grants → 当作非前缀 → 落主属 team-X 的 `team-z-slug/gpt-4o`（一般 422，因为这名字没注册） |

**关键性质**：
1. **唯一性**：同一 `(effective_team_id, model_name)` 组合通过 [resolve_by_name_visible](file:///e:/project/ai-agent/backend/domains/gateway/application/gateway_model_listing.py#L97) 唯一命中，**同名不冲突**
2. **缓存隔离**：[resolve_model_cache](file:///e:/project/ai-agent/backend/domains/gateway/application/resolve_model_cache.py) 的 key `(tenant_id, name, user_id)` 含 tenant_id，多 team 同名缓存项天然分桶
3. **零隐式跨 team**：Task 4 已关闭 [_resolve_personal_team_model](file:///e:/project/ai-agent/backend/domains/gateway/application/model_or_route_resolution.py#L180) 跨 grants fallback —— 同名模型**不会**在主属缺失时摸到 grant team，杜绝歧义
4. **审计可分辨**：`gateway_request_logs.tenant_id == effective_team_id`，配合 `client_raw_model` 与 `gateway_dispatched_via_prefix` 标志，事后可精确还原"哪一次调用打到了哪个 team 的同名模型"

**前端 UX 增强**（防止用户调错 team）：
- [key-grants-drawer.tsx](file:///e:/project/ai-agent/frontend/src/features/gateway-keys/grants/) 在每个授权 team 下展示该 team 已注册的模型列表（调 [GatewayModel listing](file:///e:/project/ai-agent/backend/domains/gateway/application/gateway_model_listing.py)）
- 当 vkey 在多个授权 team 下检测到**同名模型**时，在抽屉顶部显示 Banner："模型 `gpt-4o` 同时存在于 team-X / team-Y，请使用 `<team-slug>/gpt-4o` 显式调用以避免落到主属"
- [virtual-key-reveal-dialog.tsx](file:///e:/project/ai-agent/frontend/src/features/gateway-keys/virtual-key-reveal-dialog.tsx) 的调用示例同步给出带 prefix 的范本

**Strict 模式联动**：当 `gateway_vkey_strict_team_prefix=True`（详见 Task 3），客户端在多 grant 场景下若不带前缀**且**该 model 名同时存在多个 grant team 时直接拒绝（避免静默路由到主属）；非 strict 模式下保持"无前缀=主属"的确定性行为不变。

**审计指标补强**：在 metrics 中加 `gateway_vkey_ambiguous_model_invocations_total{vkey_id, model_name}` —— 统计"无前缀调用 + 该 model 同时存在 ≥2 个 grant team"的次数，运营据此判断是否要切 strict。

---

## Task 7.6 — 对模型自动导入链路的影响（边界外，不变量声明）

**结论：本方案不修改任何模型导入代码路径，现有 7 道防线完全保留**。

**现有导入链路参考**（[CredentialUpstreamCatalogService](file:///e:/project/ai-agent/backend/domains/gateway/application/management/credential_upstream_catalog.py)）：
1. **support 四态**：probe 返回 `full / partial / unsupported / error`，凭据解密失败不出站请求
2. **预检重名**：导入前查 `(tenant_id, name)` 是否已存在，重名走 `format_already_registered_reason` 进 `failed` 清单
3. **唯一约束保护**：[gateway_models](file:///e:/project/ai-agent/backend/domains/gateway/infrastructure/models/gateway_model.py#L102) `uq_gateway_models_tenant_name` 冲突 → `ConflictError`（409）而非裸 IntegrityError 500
4. **上游名规范化**：[normalize_upstream_model_id](file:///e:/project/ai-agent/backend/domains/gateway/domain/upstream_model_name_normalize.py)（cmecloud 大小写/符号敏感）保证 `real_model` 与上游实际接受名一致
5. **领域异常可读化**：`ValidationError` / `HttpMappableDomainError` → `failed[].reason`（用户可读）
6. **未预期异常兑底**：`except Exception` → 记 `logger.exception` + “导入失败（内部错误）”通用文案，单行失败不会中断整批
7. **前端分片**：[credential-upstream-models-panel.tsx](file:///e:/project/ai-agent/frontend/src/features/gateway-credentials/credential-upstream-models-panel.tsx#L75) 团队 50/个的 chunk，避免单请求超时

**与本方案唯一的交靠点**：
- 导入出去的模型写入 `gateway_models.tenant_id = team.id`，与 vkey grants 无关；模型导入后是否能被 vkey 调用仍走 [resolve_by_name_visible](file:///e:/project/ai-agent/backend/domains/gateway/application/gateway_model_listing.py#L97) 原逻辑
- **reserved slug 拦截**（Task 3）只拦 team 创建/改名，**不拦**模型导入；已存在的 team（slug 名不在 reserved 列表）导入路径零变动

**不变量验证（部署后烟雾测试）**：
```bash
# 以主属 team 运行 probe + batch-import，验证 created/failed 与上线前等价
POST /api/v1/gateway/teams/{team_id}/credentials/{credential_id}/probe
POST /api/v1/gateway/teams/{team_id}/credentials/{credential_id}/batch-import-models
# 同一个 credential 在跨 grant team 场景下仍只能导入到其本身 scope_id 所属 team
```

**如果导入出现问题的检查顺序**（与本方案无关，沿用现有诊断所则）：
1. 查 `failed[].reason` → 区分 “已存在” / “验证失败” / “映射缺失” / “内部错误”
2. “内部错误” → 查 logger 中同 `upstream_model_id` 的 `logger.exception` 栈迹
3. “上游 model_id 不被接受” → 查 [upstream_model_name_normalize.py](file:///e:/project/ai-agent/backend/domains/gateway/domain/upstream_model_name_normalize.py) 是否需补映射表（cmecloud 同类问题均走该一点）
4. “probe support=error” → 凭据解密失败或 base_url/scheme 不受信任，不出站检查

---

## Task 8 — 测试

**单测** `backend/tests/unit/gateway/`：
- `test_vkey_team_resolution.py` — dispatch 各分支：无前缀 / slug 命中 / 未命中 / vendor-name 与 grant slug 同名 / 空 / is_system 短路 / **多 grant team 同名 model 无前缀必落主属**
- `test_vkey_team_grant_writes.py` — 幂等 / self 撤销 422 / 非 membership 422 / system 403 / 非 owner 404
- `test_vkey_team_grant_reads.py` — active filter / is_self 总返回
- `test_virtual_key_access.py` 扩展 — header 集合内放行
- `test_model_or_route_resolution.py` 扩展 — `granted_team_ids > 1` 时跳过 `_resolve_personal_team_model`
- `test_proxy_metadata_builder.py` — `client_raw_model` 反映到 `gateway_route_name`、`gateway_dispatched_via_prefix` 标志正确

**集成测试** `backend/tests/integration/gateway/`：
1. `test_multi_tenant_vkey_dispatch_e2e.py` — 跨 team prefix 派发 + 主属 team 无该模型时 422 验证 fallback 关闭
2. `test_vkey_grants_audit_attribution.py` — 验 `gateway_request_logs.tenant_id == effective_team_id` 与 budget settle 落点
3. `test_vkey_grants_offline_cleanup.py` — 移除 membership → 跑脚本 → 调用拒绝
4. `test_vkey_grants_x_team_id_compat.py` — header 给主属/grant/非 grant 三态
5. `test_system_vkey_no_grants.py` — system vkey dispatch 短路 + grants writes 403
6. `test_vkey_grants_homonym_model.py` — **多 team 同名模型场景**：team-X / team-Y 各注册同名 `gpt-4o` 但绑不同凭据；无前缀必落 X、显式 prefix 各自命中、缓存项 `(X,gpt-4o,user)` 与 `(Y,gpt-4o,user)` 独立；strict 模式下无前缀 + 多 grant 同名 → 拒绝

---

## Task 9 — 部署与回滚

**强制部署顺序**：
1. **DB schema**：alembic upgrade（透明，旧后端不查新表）
2. **后端**：发布；自洽 grant 已回填，单元素 `granted_team_ids` 行为完全等价于旧逻辑，零回归
3. **前端**：发布 grants UI；先发也安全（API 404 时按钮 disabled）
4. **离线任务**：注册 cron `*/5 * * * *`

**兼容性矩阵**：

| 调用 | 旧 | 新 |
|---|---|---|
| `sk-gw` + `model=gpt-4o` | 落主属 | 同左 |
| `sk-gw` + `model=team-y/gpt-4o`（已 grant） | 走 personal fallback（多半失败） | 落 team-y |
| `sk-gw` + `X-Team-Id=主属` | OK | OK |
| `sk-gw` + `X-Team-Id=grant team` | 400 | 200（放宽） |
| `sk-gw` + `X-Team-Id=非 grant` | 400 | 仍 400 |
| `sk-` (platform) + `X-Team-Id` | OK | 不影响 |

**回滚顺序**：前端回退 → 后端回退 → `alembic downgrade`（顺序不可乱，避免 grant 行被丢弃）。

---

## 验证 (Verification)

**单元/集成**：
```bash
cd backend
make test-unit -- tests/unit/gateway/test_vkey_team_*.py
make test-int  -- tests/integration/gateway/test_multi_tenant_vkey_*.py
```

**端到端手测**（dev/test 环境）：
1. 用户 A 加入 team-X（创建 vkey）+ team-Y；team-Y 注册模型 `gpt-4o`
2. 调用 `POST /api/v1/gateway/teams/X/keys/{vkey_id}/grants` body `{tenant_ids: [Y.id]}` → 201
3. 用 vkey 发 `POST /v1/chat/completions {"model": "<Y.slug>/gpt-4o"}` → 200
4. 查 `gateway_request_logs WHERE vkey_id=...` → `tenant_id == Y.id`，`metadata.gateway_vkey_owner_team_id == X.id`
5. 同 vkey 发 `{"model": "gpt-4o"}` → team-X 无该模型 → 422 `GatewayModelNotFoundError`（确认 fallback 关闭）
6. 从 team-Y 移除 user A → 跑 `python -m scripts.cleanup_stale_vkey_grants` → 再次 prefix 调用 → 落主属 team-X（grants 已撤）

**Schema 检查**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 全程绿色，自洽 grant 行 count == active vkey count。

---

## 风险与未决项

1. **vendor/model 命名冲突**：reserved slug 列表（=主流 LiteLLM provider 名）需硬编码 + 单测固定；放在 [team_service.py](file:///e:/project/ai-agent/backend/domains/tenancy/application/team_service.py)。
2. **slug 变更**：当前 [Team.slug](file:///e:/project/ai-agent/backend/domains/tenancy/infrastructure/models/team.py#L26) 可改；旧客户端写死的 `old-slug/...` 改名后会落主属。**建议禁止改 slug，仅改 name**（产品确认）。
3. **离线清理窗口期**：cron 5min + remove_member 同步触发可压到秒级；建议加监控指标 `gateway_vkey_grant_stale_seconds`。
4. **EntitlementPlan scope**：现按 vkey 维度，跨 grant 调用全部享受同一 plan；用户决策 #2 暗示不做 per-grant entitlement。
5. **strict prefix 模式默认**：`gateway_vkey_strict_team_prefix=False`；上线后按误用率决定是否切默认。
6. **缓存高基数**：`gateway_route_name` 写原始 raw（含 slug 前缀）会增加 dashboard 聚合维度；建议同时落 `gateway_route_name_normalized = real_model_name` 给监控用。
7. **多 team 同名模型**：DB 层独立、路由层显式由前缀消歧、隐式 fallback 已关；非 strict 模式仍存在"用户忘加前缀 → 落主属"的确定性误用风险，需依赖前端 Banner + `gateway_vkey_ambiguous_model_invocations_total` 指标观察后切 strict（详 Task 7.5）。

---

## 关键文件速查表

| 主题 | 文件 |
|---|---|
| Alembic | [backend/alembic/versions/20260605_vkey_team_grants.py](file:///e:/project/ai-agent/backend/alembic/versions/) |
| ORM | [virtual_key_team_grant.py](file:///e:/project/ai-agent/backend/domains/gateway/infrastructure/models/) |
| Repo | [virtual_key_team_grant_repository.py](file:///e:/project/ai-agent/backend/domains/gateway/infrastructure/repositories/) |
| Dispatch 纯函数 | [vkey_team_resolution.py](file:///e:/project/ai-agent/backend/domains/gateway/application/) |
| Reads / Writes | [management/virtual_key_team_grant_reads.py](file:///e:/project/ai-agent/backend/domains/gateway/application/management/) / [..._writes.py](file:///e:/project/ai-agent/backend/domains/gateway/application/management/) |
| Schemas / Router | [presentation/schemas/grants.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/schemas/) / [routers/virtual_key_grants.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/routers/) |
| Principal 字段 | [domain/types.py:VirtualKeyPrincipal](file:///e:/project/ai-agent/backend/domains/gateway/domain/types.py) |
| Header guard | [virtual_key_access.py:assert_vkey_team_header_compatible](file:///e:/project/ai-agent/backend/domains/gateway/domain/virtual_key_access.py#L83) |
| Deps grant 加载 | [presentation/deps.py:_gateway_principal_from_vkey_plain](file:///e:/project/ai-agent/backend/domains/gateway/presentation/deps.py#L100) |
| ProxyContext 加 raw_model | [application/proxy_context.py](file:///e:/project/ai-agent/backend/domains/gateway/application/) |
| Router dispatch 接线 | [openai_compat_router.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/) / [anthropic_compat_router.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/) / [proxy_request_context.py](file:///e:/project/ai-agent/backend/domains/gateway/presentation/) |
| Fallback 闸刀 | [model_or_route_resolution.py:_resolve_model_or_route_uncached](file:///e:/project/ai-agent/backend/domains/gateway/application/model_or_route_resolution.py#L196) |
| Reserved slug | [tenancy/application/team_service.py](file:///e:/project/ai-agent/backend/domains/tenancy/application/team_service.py) |
| 离线脚本 | [backend/scripts/cleanup_stale_vkey_grants.py](file:///e:/project/ai-agent/backend/scripts/) |
| 同步触发 | [team_service.remove_member](file:///e:/project/ai-agent/backend/domains/tenancy/application/team_service.py) |
| 前端 API | [frontend/src/api/gateway/keys.ts](file:///e:/project/ai-agent/frontend/src/api/gateway/keys.ts) |
| 前端 grants 子目录 | `frontend/src/features/gateway-keys/grants/` |
| 前端 reveal hint | [virtual-key-reveal-dialog.tsx](file:///e:/project/ai-agent/frontend/src/features/gateway-keys/virtual-key-reveal-dialog.tsx) |
