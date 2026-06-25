# API 全局约定

## 服务地址

- **线上默认**：`https://gateway.giimallai.com/ai-agent/api/v1`（脚本 `gateway_client.py` 与 SKILL.md 已内置）。
- **本地开发**：`http://localhost:8000/ai-agent/api/v1`（设置环境变量 `GATEWAY_BASE_URL` 切换）。
- **认证凭证**：环境变量 `GATEWAY_API_KEY`（推荐，平台 API Key）或 `GATEWAY_TOKEN`（兼容回退）。

## 路径前缀

- **完整前缀**：`/ai-agent/api/v1`（`ROOT_PATH=ai-agent` + `api_prefix=/api/v1`）。
- **网关管理前缀**：`/ai-agent/api/v1/gateway/*`。团队管理路由 `teams_router` 也挂在此前缀下（路径 `/gateway/teams*`）。
- **团队作用域**：`/gateway/teams/{team_id}/*`，路径中显式携带 team_id。
- **个人作用域**：`/gateway/my-*`，无路径 team_id，后端自动解析到当前用户的 personal team。

> 以下文档中端点路径省略 `/ai-agent/api/v1` 前缀；客户端脚本会自动拼接 `GATEWAY_BASE_URL`。

## 认证

管理面端点（`/api/v1/gateway/*` 等所有非代理端点）支持两种认证方式：

### 1. 平台 API Key（推荐，自动化运维）

- **格式**：`sk_<16hex>_<32hex>`，在设置页 → API Key 创建，勾选 `gateway:admin` + `gateway:read` scope（或 `gateway_full` 分组）。
- **传递**：`Authorization: Bearer sk_xxxxxxxx_xxxxxxxxxxxx`（与 JWT 同样的 Bearer 头）。
- **scope 校验**：
  - 读操作（GET/HEAD/OPTIONS）：需 `gateway:read` 或 `gateway:admin`
  - 写操作（POST/PATCH/PUT/DELETE）：需 `gateway:admin`
  - 缺失 scope 返回 `403 FORBIDDEN`，code `PERMISSION_DENIED`
- **身份映射**：API Key 关联的 user 的平台角色（`admin`/`user`/`viewer`）与团队成员角色（`owner`/`admin`/`member`）自动复用，权限校验与 JWT 用户一致。
- **有效期**：创建时指定（1-365 天），不会像 JWT 那样短期过期，适合长期自动化。撤销方式：设置页禁用/删除。
- **实现位置**：`domains/identity/application/principal_service.py:_principal_from_api_key`，在 `get_principal` 中识别 `sk_` 前缀走此路径。

### 2. JWT（前端交互）

- **获取**：`POST /api/v1/auth/token`，请求体 `{email, password}`，响应 `access_token` 字段。
- **传递**：`Authorization: Bearer eyJhbGciOi...`
- **有效期**：默认数小时（`jwt_expire_hours` 配置），过期返回 401 需重新登录。
- **刷新**：`POST /api/v1/auth/token/refresh`，请求体 `{refresh_token}`。

### 不接受的认证方式

- **vkey（`sk-gw-`）**：仅用于 `/api/v1/openai/v1/*` 代理端点，管理面不识别。
- **带 `gateway:proxy` scope 的 `sk_`**：仅用于代理端点；管理面要求 `gateway:admin`/`gateway:read` scope。
- **匿名**：所有管理面端点不支持匿名，无凭证返回 401。

## RBAC 权限模型

### 平台角色（`domains/identity/domain/rbac.py:Role`）

| 角色 | 权限 |
|------|------|
| `admin` | 平台全权，可操作系统级资源 |
| `user` | 普通用户 |
| `viewer` | Gateway 管理面只读（写操作被 `assert_gateway_write_allowed` 拦截） |

### 团队角色（`TeamRole`）

| 角色 | 权限 |
|------|------|
| `owner` | 团队全权，可删团队、管理成员、管理路由 |
| `admin` | 团队管理（凭据/模型/路由/配额写操作） |
| `member` | 团队成员，可读、可管理本人 BYOK 凭据与个人配额 |

### 依赖别名速查

| 别名 | 含义 |
|------|------|
| `RequiredAuthUser` | 必须携带有效 JWT 的注册用户 |
| `AdminUser` | 必须 `Role.ADMIN` |
| `CurrentTeam` | 解析当前团队上下文（路径 team_id > `X-Team-Id` 头 > personal team） |
| `RequiredTeamMember` | 至少 team `member`（含 owner/admin） |
| `RequiredTeamAdmin` | 必须 team `owner` 或 `admin`（或平台 admin） |
| `RequiredTeamOwner` | 必须 team `owner`（或平台 admin） |

## 团队上下文解析

`domains/tenancy/presentation/team_dependencies.py` 的 `resolve_current_team` 按优先级解析：

1. 路径参数 `{team_id}`（最高优先级）
2. 请求头 `X-Team-Id`
3. 当前用户的 personal team（回退）

`ManagementTeamContext`（`domains/tenancy/domain/management_context.py`）封装解析结果，含 `team_id`、`team_kind`、`team_role`、`user_id`、`is_platform_admin`。

## 个人工作区（personal team）

- `kind="personal"`，由 `TeamService.ensure_personal_team` 幂等创建（注册时或首次访问 `/my-*` 端点时）。
- 不可手动创建或删除。
- `/my-*` 端点隐式操作 personal team，无需传 team_id。

## 凭据加密

- `api_key` 明文入参，服务端用 Fernet 加密落库到 `api_key_encrypted`（密钥从 `settings.secret_key` 派生，`libs.crypto.encrypt_value`）。
- 普通响应只返回 `api_key_masked`（脱敏）；明文需显式调 `/reveal` 端点。

## 响应格式

### 成功响应

- `GET` 列表：分页结构 `{items, total, page, page_size, has_next, has_prev}`（见 `libs/api/pagination.py`）。
- `POST` 创建：`201 Created` + 资源对象。
- `DELETE`：通常 `204 No Content` 无响应体。
- 测试/探测类：`200 OK` + 含 `success`/`support` 字段的对象（失败也返回 200）。

### 错误响应

统一 JSON 格式：

```json
{
  "error": {
    "code": "<CODE>",
    "message": "人类可读信息",
    "details": {}
  }
}
```

HTTP 状态码映射：

| code | HTTP | 含义 |
|------|------|------|
| `UNAUTHORIZED` | 401 | 未认证或 token 无效 |
| `FORBIDDEN` | 403 | 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `VALIDATION_ERROR` | 422 | 请求参数校验失败 |
| `CONFLICT` | 409 | 唯一约束冲突等 |
| `RATE_LIMITED` | 429 | 频率限制（如模型测试每分钟 1 次） |
| `INTERNAL_ERROR` | 500 | 服务端错误 |

## 通用数据约定

- **时间**：ISO 8601 datetime（带时区），如 `2026-06-24T06:26:45Z`。
- **UUID**：字符串形式 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`。
- **金额**：`limit_usd` 等用 `Decimal`（字符串传输），如 `"100.00"`。
- **分页参数**：`page`（>=1）、`page_size`（1..`MAX_PAGE_SIZE`）。
