# 路由操作（个人工作区与跨团队）

路由（`gateway_routes` 表）是虚拟模型到真实模型的调度规则。「个人工作区路由」绑定到用户的 personal team；「跨团队」通过 `primary_models` 引用其他团队的模型、通过 **Route Team Grants** 把整条路由发布给协作团队，或通过 **Virtual Key Grants** 授权 vkey。

## 路由调度策略（RoutingStrategy）

`simple-shuffle` / `weighted-pick` / `least-busy` / `latency-based-routing` / `usage-based-routing-v2` / `cost-based-routing`

默认 `simple-shuffle`。

## route_ref（跨团队引用格式）

`primary_models` 中的元素是 `route_ref`：
- **裸别名**：`alias`（引用 personal/system 团队模型）
- **slug 前缀**：`team-slug/alias`（引用协作团队模型）

> **⚠️ 关键**：`alias` 是模型的 `name` 字段，**不是** `real_model`。不同团队导入同一上游模型时 `name` 可能不同（如夜康用 `doubao-seedream-4.0`，祁拟用 `doubao-seedream-4-0-250828`）。创建/更新路由前务必先 `GET /my-route-callable-models` 确认可用的 route_ref，否则后端返回 400 `未注册或不可引用的模型别名`。

通过 `GET /my-route-callable-models` 获取所有可引用模型的 `route_ref` 与 `prefix_dispatchable` 标记（同名 slug 时 `prefix_dispatchable=false`，需用裸别名）。

## 个人工作区路由

### 列出可调用模型（跨团队）

`GET /gateway/my-route-callable-models`

**认证**：`RequiredAuthUser`

**Query**：`team_id: uuid \| null`（按归属团队过滤）、`ModelListQueryDep` 通用筛选。

**响应**（`RouteCallableModelListResponse`），每项 `RouteCallableModelItem`：
- 继承 `GatewayModelResponse` 全字段
- `route_ref: str` — 写入 `primary_models` 的引用名
- `team_kind: "personal" | "shared" | "system"` — 模型归属
- `team_slug: str \| null` — 协作团队 slug（personal/system 裸别名时为 null）
- `prefix_dispatchable: bool` — 是否可安全用 `slug/` 前缀引用

### 创建个人路由

`POST /gateway/my-routes`

**认证**：`RequiredAuthUser`；后端通过 `TeamService.ensure_personal_team` 自动确保 personal team 存在。

**请求体**（`RouteCreate`）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `virtual_model` | str | 是 | 虚拟模型名（personal team 内唯一，1-200 字符） |
| `primary_models` | list[str] | 是 | 主模型列表（route_ref 形如 `slug/alias` 或裸 alias） |
| `fallbacks_general` | list[str] | 否 | 通用 fallback |
| `fallbacks_content_policy` | list[str] | 否 | 内容策略 fallback |
| `fallbacks_context_window` | list[str] | 否 | 上下文窗口 fallback |
| `strategy` | str | 否（默认 `simple-shuffle`） | 调度策略 |
| `retry_policy` | dict \| null | 否 | LiteLLM Router 重试策略 |

**响应**：`201 Created`，`RouteResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | uuid | 路由 ID |
| `tenant_id` | uuid | - |
| `team_id` | uuid | personal team ID |
| `source` | str | `team`/`system` |
| `virtual_model` | str | 虚拟模型名 |
| `primary_models` | list[str] | 主模型 |
| `fallbacks_general` | list[str] | - |
| `fallbacks_content_policy` | list[str] | - |
| `fallbacks_context_window` | list[str] | - |
| `strategy` | str | 调度策略 |
| `retry_policy` | dict \| null | - |
| `enabled` | bool | 是否启用 |

**跨团队创建示例**：

```bash
# 先获取可引用模型
curl "$BASE/gateway/my-route-callable-models" -H "Authorization: Bearer $TOKEN"

# 创建引用多个团队模型的路由
curl -X POST "$BASE/gateway/my-routes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "virtual_model": "my-smart-router",
    "primary_models": ["rd-team/gpt-4o", "data-team/claude-3-5-sonnet"],
    "strategy": "weighted-pick"
  }'
```

### 其他个人路由端点

| 操作 | 方法 | 路径 |
|------|------|------|
| 列出个人路由 | `GET` | `/gateway/my-routes` |
| 更新个人路由 | `PATCH` | `/gateway/my-routes/{route_id}` |
| 删除个人路由 | `DELETE` | `/gateway/my-routes/{route_id}` |

## 团队级路由

路由文件：`backend/domains/gateway/presentation/routers/routes.py`

| 操作 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 列出团队路由 | `GET` | `/gateway/teams/{team_id}/routes` | `CurrentTeam` |
| 创建团队路由 | `POST` | `/gateway/teams/{team_id}/routes` | `RequiredTeamAdmin` |
| 更新团队路由 | `PATCH` | `/gateway/teams/{team_id}/routes/{route_id}` | `RequiredTeamAdmin` |
| 删除团队路由 | `DELETE` | `/gateway/teams/{team_id}/routes/{route_id}` | `RequiredTeamAdmin` |

## 跨团队 vkey 授权（Virtual Key Grants）

另一种跨团队共享方式：把 vkey 授权到其他团队，让其他团队用该 vkey 调用模型。

路由文件：`backend/domains/gateway/presentation/routers/virtual_key_grants.py`、Schema `schemas/grants.py`

| 操作 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 列出 vkey 所有 grant | `GET` | `/gateway/teams/{team_id}/keys/{key_id}/grants` | `CurrentTeam` |
| 批量授权 vkey 到 team | `POST` | `/gateway/teams/{team_id}/keys/{key_id}/grants` | 仅 vkey 创建者 |
| 撤销 grant | `DELETE` | `/gateway/teams/{team_id}/keys/{key_id}/grants/{tenant_id}` | 不可撤销 self-grant |
| 列出可授权团队 | `GET` | `/gateway/teams/{team_id}/keys/{key_id}/grants/grantable-teams` | - |

### 授权请求体

`VirtualKeyGrantBatchRequest`：`tenant_ids: list[uuid]`（1-50）

**响应**：`list[VirtualKeyTeamGrantResponse]`，含 `id`、`vkey_id`、`tenant_id`、`is_self`、`created_at`、`revoked_at`、`granted_team_name`、`granted_team_slug`、`model_count`、`registered_model_names`。

> 创建 vkey 时也可在 `VirtualKeyCreate.granted_team_ids`（最多 50 个）一次指定额外授权工作区。

## 跨团队路由共享（Route Team Grants）

**委派模式**：owner 把路由发布给协作团队，消费方以 **暴露别名** 调用；上游凭据按 owner 解析，**计费归消费团队**。与 vkey grant 互补：vkey 共享调用令牌，route grant 共享虚拟路由能力。

路由文件：`backend/domains/gateway/presentation/routers/my_routes.py`（owner 侧）、`routes.py`（consumer 侧）；Schema `schemas/route_grants.py`

| 操作 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 列出路由的全部 grant | `GET` | `/gateway/my-routes/{route_id}/grants` | 路由 owner |
| 发布路由到团队 | `POST` | `/gateway/my-routes/{route_id}/grants` | 路由 owner |
| 修改暴露别名 | `PATCH` | `/gateway/my-routes/{route_id}/grants/{tenant_id}` | 路由 owner |
| 撤销 grant | `DELETE` | `/gateway/my-routes/{route_id}/grants/{tenant_id}` | 路由 owner |
| 列出可共享团队 | `GET` | `/gateway/my-routes/{route_id}/grantable-teams` | 路由 owner |
| 列出共享进团队的路由 | `GET` | `/gateway/teams/{team_id}/shared-routes` | `CurrentTeam` |
| 踢出共享路由 | `DELETE` | `/gateway/teams/{team_id}/shared-routes/{grant_id}` | `RequiredTeamAdmin` |

### 发布请求体

`RouteGrantCreate`：`target_tenant_id: uuid`（必填）、`exposed_alias: str | null`（可选，默认路由 `virtual_model`）

**响应**（`RouteGrantResponse`）：`route_id`、`tenant_id`、`exposed_alias`、`granted_team_name`、`granted_team_slug`、`created_at`。

> 功能开关：`gateway_route_sharing_enabled`（默认 true）。关闭后 grant 不可解析、列表不暴露。

## 跨团队路由聚合

| 操作 | 方法 | 路径 |
|------|------|------|
| 跨团队路由聚合 | `GET` | `/gateway/managed-team-routes` |
| 跨团队 vkey 聚合 | `GET` | `/gateway/managed-team-keys` |

## 关键文件

- 路由：`backend/domains/gateway/presentation/routers/my_routes.py`、`routes.py`、`virtual_key_grants.py`、`virtual_keys.py`、`managed_team_routes.py`、`managed_team_virtual_keys.py`
- Schema：`backend/domains/gateway/presentation/schemas/common.py`、`grants.py`
- ORM：`backend/domains/gateway/infrastructure/models/gateway_route.py`、`gateway_route_team_grant.py`、`virtual_key.py`、`virtual_key_team_grant.py`
