# 凭据操作

凭据支持三种 scope：
- **team**：租户凭据，落 `provider_credentials` 表 + `tenant_id`
- **system**：平台凭据，落 `system_provider_credentials` 表，仅 PlatformAdmin
- **user**：用户 BYOK，落 `provider_credentials` 表 + `scope='user'`

## Provider 白名单

### 团队/系统凭据（`MANAGED_GATEWAY_CREDENTIAL_PROVIDERS`）

`openai` / `anthropic` / `azure` / `bedrock` / `gemini` / `vertex_ai` / `dashscope` / `deepseek` / `volcengine` / `zhipuai` / `moonshot` / `cohere` / `mistral` / `fireworks` / `together_ai`

### 个人 BYOK 凭据（`USER_GATEWAY_CREDENTIAL_PROVIDERS`）

`openai` / `anthropic` / `dashscope` / `zhipuai` / `deepseek` / `volcengine` / `moonshot`

> provider 必须在对应白名单内，否则 `VALIDATION_ERROR`。

## 上游 Profile（profile_id）

- SSOT：`domains/gateway/domain/upstream_profile_registry.py`
- 通过 `GET /gateway/provider-profiles` 列举，含 `api_bases`、`models_list_path`、`default_call_shape`、`probe_strategy`、`probe_supported`。
- `profile_id` 决定 `api_base` 默认值、探测策略、出站调用形态。省略时用 `<provider>.default`。
- 例：`volcengine.coding_plan`、`openai.default`。

## 创建团队/系统凭据

`POST /gateway/teams/{team_id}/credentials`

**认证**：`CurrentTeam`；`scope=system` 时必须 `is_platform_admin=true`（`assert_system_credential_mutation_allowed`）；`viewer` 平台角色被拦截。

**请求体**（`ManagedCredentialCreate`）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `provider` | str | 是 | 提供商标识（小写，须在白名单） |
| `name` | str | 是 | 展示名（同 scope 下 provider+name 唯一） |
| `api_key` | str | 是 | 明文 API Key（服务端 Fernet 加密） |
| `api_base` | str \| null | 否 | OpenAI-compat base URL |
| `api_bases` | object \| null | 否 | 协议端点覆盖 `{openai_compat, anthropic_native}` |
| `profile_id` | str \| null | 否 | 上游方案 ID；省略用 `<provider>.default` |
| `extra` | dict \| null | 否 | 扩展：endpoint_id/region/org/project_id 等 |
| `scope` | `"team"` \| `"system"` | 否（默认 `team`） | 写入目标 |

**响应**：`201 Created`，`CredentialResponse`

关键响应字段：
- `id`、`tenant_id`、`scope`、`scope_id`、`provider`、`name`
- `api_base`、`api_bases`、`profile_id`、`profile_label`
- `effective_api_base_openai`、`effective_api_base_anthropic`
- `extra`、`is_active`、`is_config_managed`、`visibility`
- `created_by_user_id`、`created_by_label`、`created_at`
- `api_key_masked`（脱敏）、`management_access`（`full`/`metadata`）

## 创建个人 BYOK 凭据

`POST /gateway/my-credentials`

**认证**：`RequiredAuthUser`（仅 JWT）

**请求体**（`UserCredentialCreate`）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `provider` | str | 是 | 提供商（须在 BYOK 白名单） |
| `name` | str | 是 | 展示名 |
| `api_key` | str | 是 | 明文 Key |
| `api_base` | str \| null | 否 | OpenAI-compat base |
| `api_bases` | object \| null | 否 | 协议端点覆盖 |
| `profile_id` | str \| null | 否 | 上游方案 ID |
| `extra` | dict \| null | 否 | 扩展字段 |

**响应**：`201 Created`，`CredentialResponse`

## 列出凭据

| 操作 | 方法 | 路径 |
|------|------|------|
| 列团队凭据（含 system） | `GET` | `/gateway/teams/{team_id}/credentials` |
| 凭据摘要（无密钥） | `GET` | `/gateway/teams/{team_id}/credentials/summaries` |
| 个人凭据列表 | `GET` | `/gateway/my-credentials` |
| 跨团队凭据汇总 | `GET` | `/gateway/managed-team-credentials` |

- system 凭据仅平台 admin 可见。

## 凭据详情与明文

| 操作 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 凭据详情 | `GET` | `/gateway/teams/{team_id}/credentials/{credential_id}` | 含 `api_key_masked` |
| 解密明文 | `GET` | `/gateway/teams/{team_id}/credentials/{credential_id}/reveal` | 返回 `{"api_key": "..."}` |
| 个人凭据详情 | `GET` | `/gateway/my-credentials/{credential_id}` | - |

> 明文 API Key 只在 `/reveal` 返回，普通响应一律脱敏。

## 探测凭据上游支持的模型

| 操作 | 方法 | 路径 |
|------|------|------|
| 探测团队/system 凭据 | `POST` | `/gateway/teams/{team_id}/credentials/{credential_id}/probe` |
| 探测个人凭据 | `POST` | `/gateway/my-credentials/{credential_id}/probe` |

**行为**：触发上游 OpenAI 兼容 `GET /v1/models` 调用，返回上游真实可用模型列表。每次实时探测，不缓存。

**响应**（`CredentialProbeResponse`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `credential_id` | uuid | 凭据 ID |
| `probe_at` | datetime | 探测时间 |
| `support` | str | `full`/`partial`/`unsupported`/`error` |
| `upstream` | str | `openai_compatible`/`none` |
| `items` | list | 上游模型列表 |
| `message` | str \| null | 错误/提示 |
| `http_status` | int \| null | 上游 HTTP 状态码 |

`items[]`（`UpstreamModelItemResponse`）：
- `id: str` — 上游模型 ID（如 `gpt-4o`）
- `owned_by: str \| null`
- `already_registered: bool` — 是否已导入当前 team/user
- `registered_names: list[str]` — 已注册的虚拟模型别名
- `inferred_model_types: list[str]` — 推断类型（`text`/`image`/`image_gen`/`video`）

**示例**：

```bash
curl -X POST "$BASE/gateway/teams/$TEAM_ID/credentials/$CRED_ID/probe" \
  -H "Authorization: Bearer $TOKEN"
```

## 更新凭据

`PATCH /gateway/teams/{team_id}/credentials/{credential_id}`

**认证**：团队 admin 或创建者。

**请求体**（`CredentialUpdate`）：可更新 `name`、`api_key`、`api_base`、`api_bases`、`profile_id`、`extra`、`is_active`。

## 删除凭据

`DELETE /gateway/teams/{team_id}/credentials/{credential_id}`

**认证**：团队 admin 或创建者。响应 `204 No Content`。

## 凭据复制与导入

| 操作 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 从 user 凭据复制到 team | `POST` | `/gateway/teams/{team_id}/credentials/import-from-user` | 单条复制 |
| 一键导入全部 user 凭据 | `POST` | `/gateway/teams/{team_id}/credentials/import` | 批量 |
| 凭据+模型一起导入 | `POST` | `/gateway/teams/{team_id}/credentials/import-with-models` | - |
| 跨 scope 复制凭据+模型 | `POST` | `/gateway/credentials/copy-with-models` | personal↔team |

## 系统凭据可见性（仅平台 admin）

`POST /gateway/system/credentials/{credential_id}/visibility`

请求体：`{visibility: "public" | "restricted"}`。

## 关键文件

- 路由：`backend/domains/gateway/presentation/routers/credentials.py`、`my_credentials.py`、`credential_copy.py`、`managed_team_credentials.py`、`provider_profiles.py`、`system_visibility.py`
- 服务：`backend/domains/gateway/application/management/write_modules/credential_writes.py`
- Schema：`backend/domains/gateway/presentation/schemas/common.py`、`credential_upstream_catalog.py`、`credential_import.py`
- 领域：`backend/domains/gateway/domain/credential_probe.py`、`upstream_profile.py`、`upstream_profile_registry.py`
- ORM：`backend/domains/gateway/infrastructure/models/provider_credential.py`、`system_gateway.py`
