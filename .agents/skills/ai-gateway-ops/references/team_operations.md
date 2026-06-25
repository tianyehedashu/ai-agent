# 团队操作

## 数据模型

团队（`teams` 表，ORM `domains/tenancy/infrastructure/models/team.py`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | uuid | 团队 ID |
| `name` | str | 团队名称（1-100 字符） |
| `slug` | str | URL slug（唯一） |
| `kind` | str | `personal`（系统创建）/ `shared`（用户创建） |
| `owner_user_id` | uuid | 所有者 |
| `settings` | json | 团队设置 |
| `is_active` | bool | 是否激活 |

路由文件：`domains/tenancy/presentation/teams_router.py`，挂载前缀 `/gateway/teams`。

## 创建团队

`POST /gateway/teams`

**认证**：`RequiredAuthUser`（任意注册用户）

**请求体**（`TeamCreate`）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | str | 是 | 团队名称（1-100 字符） |
| `slug` | str \| null | 否 | URL slug；缺省自动生成 `team-<8hex>` |
| `settings` | dict \| null | 否 | 团队设置 JSON |

**响应**：`201 Created`，`TeamResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | uuid | 团队 ID |
| `name` | str | 团队名称 |
| `slug` | str | slug |
| `kind` | str | POST 创建恒为 `"shared"` |
| `owner_user_id` | uuid | 所有者（即当前用户） |
| `settings` | dict \| null | 设置 |
| `is_active` | bool | 是否激活 |
| `created_at` | datetime | 创建时间 |
| `team_role` | str \| null | 当前用户角色（创建后为 `"owner"`） |

**业务规则**：
- `kind` 恒为 `"shared"`，调用者自动成为 `owner`。
- personal team 不可通过此 API 创建。

**示例**：

```bash
curl -X POST "$BASE/gateway/teams" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "研发团队", "slug": "rd-team"}'
```

## 列出团队

`GET /gateway/teams`

**认证**：`RequiredAuthUser`

**响应**：当前用户可见的团队列表（含 personal + 所有 shared 成员身份）。

## 更新团队

`PATCH /gateway/teams/{team_id}`

**认证**：`RequiredTeamAdmin`

**请求体**：可更新 `name`、`slug`、`settings`、`is_active`。

## 删除团队

`DELETE /gateway/teams/{team_id}`

**认证**：`RequiredTeamOwner`

**规则**：
- 不可删除 personal team（返回 `CONFLICT`）。
- 通常需团队下无活跃资源，或级联清理。

## 成员管理

| 操作 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 列出成员 | `GET` | `/gateway/teams/{team_id}/members` | `RequiredTeamMember` |
| 添加成员 | `POST` | `/gateway/teams/{team_id}/members` | `RequiredTeamAdmin` |
| 更新成员角色 | `PATCH` | `/gateway/teams/{team_id}/members/{user_id}` | `RequiredTeamAdmin` |
| 移除成员 | `DELETE` | `/gateway/teams/{team_id}/members/{user_id}` | `RequiredTeamAdmin` |

成员角色：`owner` / `admin` / `member`。`owner` 转移需特殊处理（不可自行降级导致团队无 owner）。

## 关键文件

- 路由：`backend/domains/tenancy/presentation/teams_router.py`
- 服务：`backend/domains/tenancy/application/team_service.py`（`create_team`、`ensure_personal_team`）
- Schema：`backend/domains/tenancy/presentation/schemas/teams.py`
- ORM：`backend/domains/tenancy/infrastructure/models/team.py`
