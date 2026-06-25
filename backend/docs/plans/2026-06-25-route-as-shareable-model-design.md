# 路由即可共享模型（Route-as-Shareable-Model）设计与实施计划

> 状态：**Implemented**（2026-06-25 设计；2026-06-25 合入主分支）
> 日期：2026-06-25
> 范围：`domains/gateway`（路由/授权/代理热路径/列表/日志）、`domains/tenancy`（成员生命周期 hook）、前端 `features/gateway-models` & 路由页
> 关联：[AI_GATEWAY_DOMAIN_ARCHITECTURE.md](../AI_GATEWAY_DOMAIN_ARCHITECTURE.md) §4.1/§4.4.1/§4.5/§4.6、[gateway/DEFERRED_WRITE_CONCURRENCY.md](../gateway/DEFERRED_WRITE_CONCURRENCY.md)

---

## 1. 目标与动机

让"路由（`GatewayRoute`）对用户就像一个模型"，并支持把**个人路由（可跨多个团队引用模型）共享进一个团队**，给团队其他成员调用。

- 调用侧"路由名和模型名共用同一个 `model` 字段"**已经成立**（`resolve_model_or_route`：`GatewayModel.name` 优先、未命中按 `virtual_model` 解析）。
- 个人路由"跨团队引用模型"**已经成立**（`primary_models` 用 `{team_slug}/{model_name}` 编码，`route_model_ref` + `build_personal_route_allowed_refs`）。
- **本设计要补的唯一缺口**：把这样一条个人路由**发布/授权进团队 T**，让 T 的成员把它当普通模型调用——并把权限、限额、计费、日志、生命周期全部理清。

---

## 2. 核心设计决策（含理由）

| # | 决策点 | 选定方案 | 理由 |
|---|--------|---------|------|
| D1 | 调用授权语义 | **委派模式（service account）**：被共享路由调用时，以 owner A 的身份解析底层模型并使用 A 的凭据 | B 无需自有跨团队模型访问权，跨团队共享才真正成立；A 凭据天然承载上游访问 |
| D2 | 路由"进入团队"的形态 | **发布/授权链接**：路由仍归 A（A 的 personal team），通过显式 grant 暴露给 T | 单一真源无漂移；撤销/生命周期清晰；与 `gateway_virtual_key_team_grants` 完全对称 |
| D3 | 上游真实成本归属 | **消费团队 T**：谁用谁付，日志 `tenant_id=T`，计入 T 的 budget/用量 | A 是"能力提供方"，不替全团队埋单 |
| D4 | 授权后可触达范围 | **实时生效**：A 改路由立即对 T 生效 | 委派解析每次按 A 当前权限走 `resolve_by_name_visible`，**天然具备调用时重验**（A 失权→对应 deployment 自动不可用，fail-closed），无需快照状态 |
| D5 | T 内的调用名 | **授权时指定暴露别名**（默认 `virtual_model`，可改，T 内唯一） | 与 A 内部命名解耦；不泄露 A 的 personal slug；撞 T 本地名则拒绝 |
| D6 | 谁能发布 grant | **仅 owner A**（A 必须是 T 成员）；**移除**允许 owner A ∨ T 的 owner/admin | 发布是 A 出让凭据访问的主动行为；T 为调用埋单，应能随时踢出 |
| D7 | owner 身份存放 | `GatewayRoute.created_by_user_id`（**不**在 grant 行快照） | 所有权是路由内在属性、单一真源；与 `provider_credentials`/`gateway_models` 的 `created_by_user_id` 约定一致；热路径零额外反查 |
| D8 | 用量归人 | 日志 `user_id`=消费者 B（`usage_aggregation=user` 聚合）；`resource_owner_user_id`=A（提供方视角） | `resource_owner_user_id` 列注释即"授权共享调用时快照 users.id"，量身命中 |

**关键安全要害（D1）**：委派解析时 `resolve_by_name_visible(...)` 的 `user_id` 必须切换为 **owner A**，绝不用消费者 B。误用 B：轻则 A 模型对 B 不可见→路由 fail-closed（可接受）；重则若漏判可见性→B 越权触达。此处必须显式、独立、重点测试 + 架构守门。

---

## 3. 领域模型与 Schema

### 3.1 `GatewayRoute` 加列

```
gateway_routes
└── + created_by_user_id  UUID NULL   # 委派权威主体（路由 owner）
```

迁移回填：按 `tenant_id` 所属团队 owner（personal/team 一致），复用凭据迁移 `20260619_tccb` 的回填套路。

### 3.2 新表 `gateway_route_team_grants`（对称 `gateway_virtual_key_team_grants`）

```
gateway_route_team_grants
├── id
├── route_id            UUID NOT NULL  # refs gateway_routes.id（no DB FK）
├── tenant_id           UUID NOT NULL  # 被授权消费团队 T（refs teams.id，no DB FK）
├── exposed_alias       VARCHAR(200) NOT NULL  # T 内调用名
├── granted_by_user_id  UUID NOT NULL  # = route.created_by_user_id（守恒，审计）
├── is_active           BOOL NOT NULL DEFAULT TRUE   # 软撤销
├── revoked_at          TIMESTAMPTZ NULL
├── revoked_reason      VARCHAR(40) NULL  # owner_revoked | team_admin_revoked | membership_lost | team_archived | route_deleted
└── created_at / updated_at
```

约束 / 索引（部分唯一索引仅约束 active 行，与 vkey grant 一致）：
- `uq_route_team_grants_active`：`(route_id, tenant_id) WHERE is_active`
- `uq_route_team_grants_alias_active`：`(tenant_id, exposed_alias) WHERE is_active`
- `ix_route_team_grants_tenant_active`：`(tenant_id) WHERE is_active`（Router 装配/列表扫描）
- `ix_route_team_grants_route_active`：`(route_id) WHERE is_active`
- `ix_route_team_grants_user_tenant_active`：`(granted_by_user_id, tenant_id) WHERE is_active`（成员移除时撤销）

**与 vkey grant 的差异**：无 `is_self`（路由 grant 目标永远是 A 所在的 shared team T，不存在自洽行）。

不纳入本期（YAGNI）：`system_gateway_routes` 的团队授权（系统可见性已有 `system_gateway_grants`）。

---

## 4. 代理热路径（最核心、最高风险）

### 4.1 解析：`application/model_or_route_resolution.py`

`resolve_model_or_route(session, team_id=T, name=X, user_id=B)` 在现有"本地 model → personal fallback → 本地 route"**全部 miss** 之后，新增 **granted-route 分支**：

1. `GatewayRouteGrantRepository.resolve_by_tenant_alias(T, X)` → 命中 active grant → 取 `route` 与 `owner = route.created_by_user_id`（= A）。
2. **委派解析**：以 `user_id=A`、route_owner = A 的 personal team 解析 `route.primary_models`（`_resolve_route_primary_record` 复用，仅切换主体）。
3. 返回 `ResolvedModelName(record=A 的主选模型, route=route, via_route=X)`；capability 用主选模型校验，与现状一致。

缓存（`resolve_model_cache`）key 仍为 `(team_id=T, name=X, user_id=B)`：委派结果与 B 无关，但按 B 缓存仍正确（共享度略低，可接受）。返回的是 cache-safe 快照（已有机制）。

### 4.2 Router 装配：`infrastructure/router_singleton.py`

- `_build_router_kwargs`：额外加载 active route grants（`list_active_for_router`）。
- `_routes_to_virtual_deployments` 重构为接受三元组 `(route, resolve_owner_tenant=A, target=(tenant=T, name=alias))`：
  - **引用解析 owner = A**（route_owner tenant + A 的 slug context）→ 决定底层模型/凭据；
  - **deployment 命名空间 = T/alias** → `model_name = encode_router_model_name(T, alias)`。
  - 现有恒等路径 = `target=(A, virtual_model)` 的特例。
- `route_slug_contexts` 需包含 grant 路由的 owner tenant（扩展 `route_owner_ids` 收集范围）。
- 价目注入（`_load_upstream_pricing_lookup`）对 grant deployment 同样生效（复用现成 lookup）。

于是 `prepare_litellm_kwargs` 对 `(T, X)` 编出的 `gw/t/{T}/{X}` 命中这些**用 A 凭据**的 deployment。

### 4.3 计费 / 归因：`application/proxy_metadata_builder.py`

- `ctx.team_id` 始终是 T → 预算/用量/日志 `tenant_id=T`（成本归 T）。
- metadata 写 `resource_owner_user_id = A`（复用既有日志列，**不新增列**）。
- `route_snapshot` 注入 grant 上下文：`{delegated=true, route_grant_id, exposed_alias, owner_user_id=A, owner_tenant_id, virtual_model, primary_models, strategy, ...}`（`build_delegated_route_snapshot_metadata`；`route_grant_id` 经 `ResolvedModelName.delegated_grant_id` 贯穿）。
- deployment metadata 仍写 A 的 `gateway_credential_*`（上游归因）。
- 委派下的凭据归因/route_snapshot 走 **grant 感知**：`get_route_snapshot_metadata(session, T, X)` 按 `(T, virtual_model)` 必 miss（路由在 A 租户下），故委派路径**不复用该缓存**，由 `build_delegated_route_snapshot_metadata` 以已解析 owner 路由直建（零额外查库，快照构形仍单一真源于 domain）。

### 4.4 范围收敛（v1）

先只把 **primary_models 负载均衡组** 暴露到 T/alias；路由 `fallbacks_*` 链在 T 命名空间下的复刻留作 follow-up（涉及 LiteLLM model_group fallback 跨命名空间映射，复杂度高、收益边际）。

---

## 5. 读路径与列表暴露（让路由在 T 里像个 model）

统一**投影**：把 granted route 投影成"类 model 列表项"，复用现有列表管线。

- 新 `application/granted_route_listing.py` + `proxy_model_list_reads`（纯函数投影）：`id/name = exposed_alias`；`capability/model_types/selector_capabilities` 取**路由主选模型快照**；嵌套 `gateway.kind="route"`、`via_route`、`shared_from`（owner A 展示名/来源）；`callable` 按 **A 身份**下底层 primaries 当前可解析/连通判定（A 失权→`callable=false`，透明列出）。
- 接入三条读路径：
  - `GET /api/v1/openai/v1/models`（`vkey_proxy_model_list` / `proxy_model_list_reads.build_proxy_models_list`）：并入 T 的 granted route 投影项；别名 T 内唯一保证无冲突。✅
  - `GET /api/v1/gateway/models/available`（聊天选择器，`gateway_team_id=T`）：经 `granted_route_selector_items.list_granted_route_selector_items` 并入 `system_models`；代表 primary 模型走 `gateway_model_to_selector_item`，条目 `id=暴露别名`、附 `is_shared_route=true`。✅
  - `GET /api/v1/gateway/teams/{team_id}/models`（管理 UI）：**未**内嵌只读芯片；改由前端独立 `shared-routes-panel.tsx`（T 侧共享路由列表 + admin 移除）承载，意图等价（**有意偏移**）。
- vkey 白名单：`X` 是普通 `model` 字符串，T 的 vkey `allowed_models` 可直接勾选；代理面 `assert_model_allowed` 用客户端字面量校验，天然通过。

---

## 6. 权限·限额·计费·生命周期矩阵

### 6.1 账目与限额轴

| 轴 | 归属 | 载体 | 耗尽语义 |
|----|------|------|---------|
| 下游 Entitlement | 消费者 B 的 vkey/grant | `entitlement_plans`（按 vkey） | 429 硬拒 |
| 预算 Budget | **消费团队 T** | `gateway_budgets`（team=T / user=B / key=B vkey） | 拒绝 |
| 上游 ProviderPlan | **A 的凭据** | `provider_plans` | deployment cooldown，Router 内 fallback |
| 限流 RPM/TPM | 双层 | B vkey 限流 + A 底层模型 `rpm/tpm` | 各层各自触发 |
| 成本 / 收入 | 上游计 A 凭据、**计入 T 用量** | 日志 `tenant_id=T`、`credential_id=A`、`resource_owner_user_id=A`、`user_id=B` | — |

**不变量**：A 自己的 personal team 预算/Entitlement **不被触碰**；A 侧唯一约束是其凭据上的厂商 ProviderPlan。

**用量归人粒度**：能精确到人取决于**入站身份**——平台 API Key(`sk-*`)/JWT/Agent 天然带 `user_id`；vkey(`sk-gw-*`) actor 是 vkey 本身（`vkey_id`+`vkey_name_snapshot`），一 key 多人则只能精确到 key。此为平台既有语义，非本方案引入。

### 6.2 RBAC

| 动作 | 谁 |
|------|----|
| 发布路由→T（创建 grant） | 仅 owner A（A 必须是 T 成员） |
| 改暴露别名 | owner A |
| 移除 grant（取消发布 / 踢出团队） | owner A ∨ T 的 owner/admin |
| 编辑路由本身 | 仅 A（T 侧只读） |

### 6.3 生命周期与退化（无 DB FK + 生命周期端口 + 离线清理，对称 vkey grant）

| 事件 | 处理 | revoked_reason |
|------|------|----------------|
| A 失去某底层团队成员资格 | 委派解析对该 primary 返回 None → deployment 不可用；其余 primary 仍服务；全失则 `callable=false`（fail-closed） | —（运行时自然降级，不撤 grant） |
| 底层模型下线/禁用 | Router 装配跳过；同上 | — |
| A 删除路由 | 级联软撤销该路由所有 grant + `reload_router` | `route_deleted` |
| A 被移出团队 T | `RouteGrantLifecyclePort.revoke_for_membership_lost(A, T)`，删成员前先撤 | `membership_lost` |
| T 被删 | `revoke_for_team_deleted(T)` | `team_archived` |
| owner / T admin 主动撤 | 软撤销 | `owner_revoked` / `team_admin_revoked` |
| grant 悬空（路由/团队已删但残留） | 离线脚本 set-based 清理 | — |
| T 新建本地 model/route 撞 granted alias | 本地创建侧**反向别名冲突校验**拒绝 | — |

---

## 7. 改造清单（文件级落点）

### 7.1 Schema / 迁移（alembic 两步）
- [x] `alembic/versions/20260702_route_team_grants.py`：`gateway_routes` 加 `created_by_user_id`（回填团队 owner）+ 建 `gateway_route_team_grants` + 索引。
- [x] 日志侧 **0 新列**（grant 上下文进 `route_snapshot` JSONB；复用 `resource_owner_user_id`）。

### 7.2 Domain
- [x] `infrastructure/models/gateway_route.py`：加 `created_by_user_id`。
- [x] 新 `infrastructure/models/gateway_route_team_grant.py`（`GatewayRouteTeamGrant`，软删除 + `revoke()`），注册进 `infrastructure/models/__init__.py`。
- [x] 新 `domain/policies/route_grant_access.py`（纯规则）：create=owner-only、remove=owner∨team admin、别名双向唯一校验。
- [x] 列表投影：`application/granted_route_listing.py` + `proxy_model_list_reads._build_route_model_list_item`（**未**单独建 `domain/route_grant_projection.py`）。

### 7.3 Infrastructure
- [x] 新 `infrastructure/repositories/gateway_route_grant_repository.py`。
- [x] `infrastructure/router_singleton.py`：加载 grants；`_routes_to_virtual_deployments` 扩展 grant deployment；`route_owner_ids` / `route_slug_contexts`。

### 7.4 Application
- [x] `application/model_or_route_resolution.py`：granted-route 分支 + **委派 swap（user_id=owner）**。
- [x] `application/proxy_metadata_builder.py`：委派路径写 `resource_owner_user_id`、`route_snapshot` grant 上下文。委派快照由 `domain/route_snapshot.build_delegated_route_snapshot_metadata`（纯函数，单一真源）以已解析 owner 路由直建；**不**复用 `route_snapshot_cache` 键空间（其按 `(consumer_team_id, virtual_model)` 查本地路由，委派场景必落空）。
- [x] 列表读：`proxy_model_list_reads.py`、`vkey_proxy_model_list.py`、`granted_route_listing.py`；聊天选择器 `granted_route_selector_items.py` 并入 `model_selector_list_reads.list_available_models_page`。
- [x] 写侧：`write_modules/route_grant_writes.py`；`model_writes` / `route_writes` 反向别名冲突校验；删路由级联软撤销 grants。
- [x] 生命周期：`RouteGrantLifecyclePort` + `route_grant_lifecycle_adapter`；`TeamService` 注入并在成员/团队删除时 revoke；撤销后 `invalidate_gateway_read_caches_for_tenant`。
- [x] bootstrap：`TeamService` 装配 `RouteGrantLifecycleAdapter`。

### 7.5 Presentation
- [x] Owner grant 端点挂载于 `presentation/routers/my_routes.py`（**未**单独 `route_grants.py`）：`GET/POST/PATCH/DELETE /my-routes/{route_id}/grants`、`GET .../grantable-teams`。
- [x] T 侧踢出：`presentation/routers/routes.py`：`GET/DELETE /teams/{team_id}/shared-routes`。
- [x] `presentation/schemas/route_grants.py`。

### 7.6 运维脚本
- [x] `scripts/cleanup_stale_route_grants.py`。

### 7.7 前端
- [x] 路由页「发布到团队」UI（`route-share-panel.tsx`）。
- [x] 模型/选择器列表共享路由项：`/v1/models` 用 `gateway.kind=route` + `shared_from`；`/models/available` 选择器项附 `is_shared_route`（芯片可选，后端字段已就绪）。
- [x] T 侧共享路由列表 + admin 移除（`shared-routes-panel.tsx`，替代管理 UI 内嵌只读芯片）。
- [x] `api/gateway/routes.ts` + `hooks/use-route-grants.ts`。
- [x] 暴露别名编辑 UI：`route-share-panel.tsx` 芯片内编辑按钮 → `RouteGrantAliasDialog`（`useUpdateRouteGrantAlias`）。

### 7.8 配置开关
- [x] `bootstrap/config.py`：`gateway_route_sharing_enabled`（默认 **true**；设计稿曾用 `gateway_route_team_grant_enabled`）。

---

## 8. 测试计划（按现有布局）

- **单元 `tests/unit/gateway/`**：`test_route_grant_access.py`、`test_route_grant_delegation.py`、`test_route_grant_lifecycle.py`（委派 swap、Router 装配、生命周期）。
- **集成 `tests/integration/gateway/`**：`test_route_grant_e2e.py`（发布→调用→列表→归因）；`test_vkey_grants_models_list.py`（multi-grant vkey 含共享路由）。

---

## 9. 分阶段上线（每步可独立合并）

| 阶段 | 内容 | 风险 |
|------|------|------|
| **P0** | Schema（`created_by_user_id` + grant 表）+ repo + 模型注册，无行为变化 | 低 |
| **P1** | grant 管理 API + RBAC + 级联/生命周期 + 离线清理（grant 可建但尚不可路由，或灰度关闭） | 低-中 |
| **P2** | 热路径：委派解析 + Router 装配（开关 `gateway_route_sharing_enabled`） | **高** |
| **P3** | 列表暴露（`/v1/models`、`/models/available`、管理 UI 只读）+ vkey 白名单 | 中 |
| **P4** | 日志富化（`resource_owner_user_id` + `route_snapshot` grant 上下文）+ 用量归人呈现 + 前端发布/芯片/移除 | 中 |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| **委派 swap 漏判 = 越权** | 解析分支独立函数 + 重点单元/集成测试 + 架构守门；code review 必须确认 `user_id=A` |
| Router 单例多 worker 不一致 | grant 增删后 `reload_router` 可达（已有 Redis 一致性机制） |
| 热路径多一次 grant 查询 | 仅本地全 miss 后查 + `resolve_model_cache` + 部分唯一索引；grant 表小 |
| grant 悬空 | 软撤销 + 生命周期端口 + 离线 set-based 清理（仿 vkey） |
| 命名空间冲突 | 别名双向唯一（本地建 model/route 与 grant alias 互斥校验） |

---

## 11. 明确不做（YAGNI / Follow-up）

- 路由 `fallbacks_*` 链在 T 命名空间下的复刻（v1 仅 primary 负载均衡组）。
- `system_gateway_routes` 的团队授权（已有 `system_gateway_grants`）。
- per-grant 维度的 EntitlementPlan / 套餐（Entitlement 仍按 vkey）。
- grant 维度的独立大盘聚合列/索引（先用 `route_snapshot` JSONB，按需再加 `route_grant_id` 列）。
