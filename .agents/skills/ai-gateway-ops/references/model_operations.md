# 模型操作

模型（`gateway_models` 表）是注册到团队的虚拟模型别名，绑定凭据与真实上游模型。能力信息存储在 `tags`（JSONB）。

## 模型能力（Model Capability）

能力位存储在 `GatewayModel.tags`，由 `selector_capabilities_from_tags`（`application/config_catalog_sync.py`）推导为扁平字段。**没有独立的"能力"端点**，通过 `PATCH` 模型的 `tags` 修改。

### 能力位清单（`ModelSelectorCapabilities`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `supports_vision` | bool | 视觉理解 |
| `supports_tools` | bool | 工具调用 |
| `supports_reasoning` | bool | 推理 |
| `thinking_param` | str | `none`/... 思考参数 |
| `temperature_policy` | str | `client`/... 温度策略 |
| `temperature_default` | float | 默认温度 |
| `supports_json_mode` | bool | JSON 模式 |
| `supports_image_gen` | bool | 图像生成 |
| `supports_txt2img` | bool | 文生图 |
| `supports_img2img` | bool | 图生图 |
| `supports_video_gen` | bool | 视频生成 |
| `supports_image_to_video` | bool | 图生视频 |
| `max_reference_images` | int | 最大参考图数 |

### 主调用面（capability）

`chat` / `embedding` / `image` / `video_generation` / `moderation` / `audio_transcription` / `audio_speech` / `rerank`

### model_types（产品特性类型）

`text` / `image` / `image_gen` / `video`，写入 `tags.supports_*`。

## 批量导入上游模型到团队（推荐）

`POST /gateway/teams/{team_id}/credentials/{credential_id}/batch-import-models`

**认证**：`CurrentTeam`（成员级写权限）

**请求体**（`TeamGatewayModelBatchImportRequest`）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `provider` | str | 是 | 提供商 |
| `capability` | str | 否（默认 `chat`） | 主调用面 |
| `weight` | int | 否（默认 1） | 路由权重，>=1 |
| `rpm_limit` | int \| null | 否 | RPM 上限 |
| `tpm_limit` | int \| null | 否 | TPM 上限 |
| `tags` | dict \| null | 否 | 标签 |
| `enabled` | bool | 否（默认 true） | 是否启用 |
| `items` | list | 是（1-50 项） | 要导入的模型 |

`items[]`（`TeamGatewayModelBatchImportItem`）：
- `upstream_model_id: str`（必填，1-200 字符）— 上游模型 ID（如 `gpt-4o`）
- `name: str \| null` — 虚拟别名；缺省由后端生成
- `owned_by: str \| null` — 模型拥有者

**响应**（`201 Created`，`TeamGatewayModelBatchImportResponse`）：
- `credential_id: uuid`
- `created: list[{upstream_model_id, gateway_model_id}]`
- `failed: list[{upstream_model_id, reason}]`

## 手动注册单个团队模型

`POST /gateway/teams/{team_id}/models`

**认证**：`CurrentTeam`。若同名模型已存在但绑定不同凭据，自动转为「追加到既有 Route」（多凭据负载均衡）。

**请求体**（`GatewayModelCreate`）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | str | 是 | 虚拟模型别名（同 team 唯一，1-200 字符） |
| `capability` | str | 是 | 主调用面 |
| `real_model` | str | 是 | 真实模型 ID（如 `deepseek/deepseek-chat`） |
| `credential_id` | uuid | 是 | 绑定凭据 ID |
| `provider` | str | 是 | 提供商 |
| `weight` | int | 否 | 权重（默认 `MIN_DEPLOYMENT_WEIGHT`） |
| `rpm_limit` | int \| null | 否 | RPM 限流 |
| `tpm_limit` | int \| null | 否 | TPM 限流 |
| `tags` | dict \| null | 否 | 标签（含 `supports_*` 能力位、`display_name`） |
| `display_name` | str \| null | 否 | 展示名（写入 `tags.display_name`） |
| `upstream_call_shape` | str \| null | 否 | `openai_compat`/`anthropic_native`；NULL 跟随凭据 profile |
| `enabled` | bool | 否（默认 true） | 是否启用 |

**响应**：`201 Created`，`GatewayModelResponse`

## 多凭据一键注册（自动建 Route）

`POST /gateway/teams/{team_id}/models/multi-credential`

请求体 `MultiCredentialGatewayModelCreate`：与 `GatewayModelCreate` 类似，但 `credential_ids: list[uuid]` 替代 `credential_id`，新增 `strategy: RoutingStrategy`（默认 `simple-shuffle`）。

响应 `MultiCredentialGatewayModelResponse`：`route_id`、`virtual_model`、`strategy`、`primary_models`、`created_model_ids`。

## 列出团队模型

`GET /gateway/teams/{team_id}/models`

**认证**：`CurrentTeam`

**Query 参数**（`ModelListQueryDep`）：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码（>=1） |
| `page_size` | int | DEFAULT | 每页数量 |
| `q` | str \| null | - | 名称/real_model 模糊搜索 |
| `connectivity` | str | `all` | `all`/`success`/`failed`/`unknown` |
| `sort` | str | `name` | `name`/`created_at`/`provider`/`last_tested_at` |
| `order` | str | `asc` | `asc`/`desc` |
| `provider` | str \| null | - | 提供商过滤 |
| `credential_id` | uuid \| null | - | 凭据过滤 |
| `type` | str \| null | - | 能力筛选（model_types 或主 capability） |
| `capability` | str \| null | - | deprecated，用 `type` |
| `enabled` | bool \| null | - | 启用状态 |
| `registry_scope` | str | `team` | `team`/`system`/`callable`/`requestable`/`system_requestable`（`system` 仅平台 admin） |

**响应**（`GatewayModelListResponse`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `items` | list | 模型列表（分页） |
| `total` `page` `page_size` `has_next` `has_prev` | - | 分页元数据 |
| `connectivity_summary` | object | `{total, available, unavailable, success, failed, unknown}` |

### GatewayModelResponse 关键字段

`id`、`tenant_id`、`team_id`、`registry_kind`（`team`/`system`）、`name`、`capability`、`real_model`、`credential_id`、`provider`、`weight`、`rpm_limit`、`tpm_limit`、`enabled`、`tags`、`upstream_call_shape`、`model_types`、`selector_capabilities`、`last_test_status`、`last_tested_at`、`last_test_reason`、`visibility`、`system_credential`、`credential_name`、`created_by_user_id`、`created_at`

## 模型详情

`GET /gateway/teams/{team_id}/models/{model_id}?registry_scope=team`

响应 `GatewayModelResponse`。

## 修改模型（含能力位）

`PATCH /gateway/teams/{team_id}/models/{model_id}`

**认证**：`CurrentTeam`（基于 `team_role` + `created_by_user_id` 判定写权限）

**请求体**（`GatewayModelUpdate`，全部可选）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str \| null | 别名（同 team 唯一） |
| `real_model` | str \| null | 真实模型 ID |
| `credential_id` | uuid \| null | 绑定凭据 |
| `capability` | str \| null | 主调用面 |
| `model_types` | list[str] \| null | 产品特性类型，写入 `tags.supports_*` |
| `weight` `rpm_limit` `tpm_limit` | - | 限流参数 |
| `enabled` | bool \| null | 启用 |
| `tags` | dict \| null | 标签（直接覆盖；改 `supports_vision`/`supports_tools`/`supports_reasoning`/`thinking_param`/`temperature_policy` 等用此字段） |
| `display_name` | str \| null | 写入 `tags.display_name` |
| `resync_capabilities` | bool | true 时从 LiteLLM `model_cost` 重算能力 tags（字段本身不持久化） |
| `upstream_call_shape` | str \| null | `openai_compat`/`anthropic_native` |

**响应**：`GatewayModelResponse`

**修改能力示例**：

```bash
curl -X PATCH "$BASE/gateway/teams/$TEAM_ID/models/$MODEL_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tags": {"supports_vision": true, "supports_tools": true, "thinking_param": "none"}}'
```

或从 LiteLLM 重算：

```bash
-d '{"resync_capabilities": true}'
```

## 批量重算能力

`POST /gateway/teams/{team_id}/models/batch-resync-capabilities`

请求体 `GatewayModelBatchResyncCapabilitiesRequest`：`model_ids: list[uuid]`（1-200）

响应 `GatewayModelBatchResyncCapabilitiesResponse`：`succeeded: list[uuid]`、`failed: list[{id, code, message}]`

## 测试模型连通性

`POST /gateway/teams/{team_id}/models/{model_id}/test`

`POST /gateway/my-models/{model_id}/test`（个人模型）

**认证**：`CurrentTeam` / `RequiredAuthUser`

**频率限制**：同一用户同一模型每分钟 1 次（`libs.rate_limit.check_probe_rate_limit`）。

**行为**：对 Gateway 模型发起一次最小调用做连通性测试，结果落库到 `gateway_models.last_test_status`/`last_tested_at`/`last_test_reason`。

**响应**（`200 OK`，`GatewayModelTestResponse`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 是否成功 |
| `message` | str | 提示信息 |
| `model` | str | 测试的模型名 |
| `status` | str | `success`/`failed` |
| `tested_at` | datetime | 测试时刻 |
| `reason` | str \| null | 失败原因（成功时 null） |
| `response_preview` | str \| null | 响应预览 |

> **成功与失败均返回 HTTP 200**，由 `success` 字段区分。

## 删除模型

### 单个删除

`DELETE /gateway/teams/{team_id}/models/{model_id}`

**认证**：`CurrentTeam`（创建者本人或团队 admin+）

**响应**：`204 No Content`。删除时级联清理 `system_gateway_grants` 与 `gateway_budgets` 相关行。

### 批量删除

`POST /gateway/teams/{team_id}/models/batch-delete`

> 注意是 `POST`（非 DELETE），便于传大 body。

**请求体**（`GatewayModelBatchDeleteRequest`）：`model_ids: list[uuid]`（1-200）

**响应**（`GatewayModelBatchDeleteResponse`）：
- `succeeded: list[uuid]`
- `failed: list[{id, code, message}]`
- `grants_removed: int`
- `budgets_removed: int`

## 跨团队复制模型

`POST /gateway/models/copy-to-team`

**认证**：`RequiredAuthUser` + `assert_gateway_write_allowed`

**请求体**（`CopyModelsToTeamRequest`）：
- `model_ids: list[uuid]`（1-200）
- `destination_team_id: uuid`
- `credential_plans: list[{source_credential_id, mode: "existing"|"copy_credential", destination_credential_id}]`（1+，`source_credential_id` 唯一）

**响应**（`CopyModelsToTeamResponse`）：`succeeded: list[{source_model_id, new_model_id, name}]`、`failed: list[{model_id, reason}]`

## 个人模型操作

| 操作 | 方法 | 路径 |
|------|------|------|
| 个人模型批量导入 | `POST` | `/gateway/my-credentials/{credential_id}/batch-import-models` |
| 列出个人模型 | `GET` | `/gateway/my-models` |
| 个人模型详情/更新 | `GET`/`PATCH` | `/gateway/my-models/{model_id}` |
| 删除个人模型 | `DELETE` | `/gateway/my-models/{model_id}` |
| 个人模型批量删除 | `POST` | `/gateway/my-models/batch-delete` |

`PersonalModelBatchImportRequest`：`provider`、`items: list[{upstream_model_id, model_types}]`（1-50）、`upstream_model_ids`（deprecated）、`model_types`（默认 `["text"]`）、`display_name_prefix`、`enabled`、`tags`。

## 跨团队聚合与预设

| 操作 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 跨团队模型聚合 | `GET` | `/gateway/managed-team-models` | 当前用户可管理团队的模型 |
| 跨团队凭据筛选 | `GET` | `/gateway/managed-team-model-credential-filters` | 筛选下拉 |
| 跨团队用量汇总 | `GET` | `/gateway/managed-team-models/usage-summary` | - |
| 模型预设目录 | `GET` | `/gateway/teams/{team_id}/models/presets` | 配置托管全局模型目录 |

## 系统模型可见性（仅平台 admin）

`PATCH /gateway/system/models/{model_id}/visibility`

请求体 `SystemModelVisibilityPatch`：`{visibility: "inherit" | "public" | "restricted"}`。

## 关键文件

- 路由：`backend/domains/gateway/presentation/routers/models.py`、`my_models.py`、`model_copy.py`、`managed_team_models.py`、`system_visibility.py`
- Schema：`backend/domains/gateway/presentation/schemas/common.py`、`model_copy.py`
- 领域：`backend/domains/gateway/domain/model_capability.py`
- ORM：`backend/domains/gateway/infrastructure/models/gateway_model.py`
