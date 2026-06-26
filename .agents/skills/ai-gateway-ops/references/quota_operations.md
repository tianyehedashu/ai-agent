# 配额与限额操作

项目用统一的 **Quota Rules** facade 把三层 quota 统一暴露：

| layer | 含义 | 落表 | 核心维度 |
|-------|------|------|----------|
| `platform` | 平台预算 | `gateway_budgets` | `target_kind`（system/tenant/key/user） |
| `upstream` | **上游凭据限额** | `provider_quotas` | `credential_id` + `model_name`（real_model） |
| `downstream` | 下游客户套餐 | `entitlement_plans` + `entitlement_plan_quotas` | vkey/apikey_grant |

> **「上游限额」= `layer="upstream"` 的 QuotaRule**，绑定凭据与厂商真实模型。这是配置凭据用量上限的入口。

## 查看配额规则（含上游）

`GET /gateway/teams/{team_id}/quota-rules`

**认证**：`CurrentTeam`；管理员可见全量，普通成员仅可见本人相关子集。

**Query 参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `page` `page_size` | int | 分页 |
| `layer` | `platform`/`upstream`/`downstream` \| null | 按层过滤；上游限额用 `upstream` |
| `user_id` | uuid \| null | 按用户过滤 |
| `credential_id` | uuid \| null | 按凭据过滤（**上游限额常用**） |
| `model_name` | str \| null | 按模型名过滤（上游对应 `real_model`） |
| `period` | `daily`/`monthly`/`total` \| null | 按周期 |
| `include_usage` | bool | 是否含当前用量 |

**响应**（`QuotaRuleListResponse`，分页），每条 `QuotaRuleResponse` 含三块：

**key**（`QuotaRuleKeyResponse`）：
- `team_id`、`layer`、`user_id`、`credential_id`、`model_name`
- `period`、`window_seconds`、`reset_strategy`、`period_timezone`、`period_reset_minutes`、`period_reset_day`
- `access_kind`（`none`/`vkey`/`apikey_grant`）、`access_id`
- `quota_label`、`target_kind`、`target_id`

**source_ref**（`QuotaRuleSourceRefResponse`）：
- `layer`、`budget_id`、`plan_id`、`quota_id`（定位底层行）

**limits**（`QuotaRuleLimitsResponse`）：
- `limit_usd`、`soft_limit_usd`、`limit_tokens`、`limit_requests`、`limit_images`
- `unit_price_usd_per_token`、`unit_price_usd_per_request`

**usage**（`QuotaRuleUsageResponse \| null`，当 `include_usage=true`）：
- `current_usd`、`current_tokens`、`current_requests`、`current_images`
- `window_start`、`reset_at`、`budget_reset_at`

附加：`plan_label`、`is_active`、`valid_from`、`valid_until`

## 批量 upsert 配额规则（含上游）

`PUT /gateway/teams/{team_id}/quota-rules/batch`

**认证**：`RequiredTeamAdmin`（团队 owner/admin 或平台 admin）；`layer=platform` + `target_kind=system` 时仍要求平台 admin。

**请求体**（`QuotaRuleBatchUpsertRequest`）：`rules: list[QuotaRuleUpsert]`（1-200）

每项 `QuotaRuleUpsert`：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `layer` | `platform`/`upstream`/`downstream` | 是 | 上游限额用 `upstream` |
| `target_kind` | `system`/`tenant`/`key`/`user` \| null | 否 | 上游通常 `tenant` 或 `user`（BYOK） |
| `target_id` | uuid \| null | 否 | target_kind=tenant 时由后端填 team_id；user 时填用户 ID |
| `user_id` | uuid \| null | 否 | 用户维度 |
| `credential_id` | uuid \| null | 否 | **上游限额核心字段**：绑凭据 |
| `model_name` | str \| null | 否 | 厂商模型字符串；NULL = 整凭据共享 |
| `period` | `daily`/`monthly`/`total` \| null | 否 | 周期 |
| `window_seconds` | int \| null | 否 | 窗口长度；0 = 累计额度 |
| `reset_strategy` | str \| null | 否 | `rolling`/`calendar_daily_utc`/`calendar_monthly_utc` |
| `period_timezone` `period_reset_minutes` `period_reset_day` | - | 否 | 重置时刻 |
| `reset_timezone` `reset_time_minutes` `reset_day_of_month` | - | 否 | 别名（plan_quota 字段） |
| `quota_label` | str \| null | 否 | 规则标签（1-40 字符） |
| `access_kind` `access_id` | - | 否 | 绑 vkey/apikey_grant |
| `included_models` | list[str] | 否 | 覆盖模型列表 |
| `limit_usd` `soft_limit_usd` `limit_tokens` `limit_requests` `limit_images` | Decimal/int \| null | 否 | 限额（至少一个）；`limit_images` 仅对 image 能力模型生效 |
| `unit_price_usd_per_token` `unit_price_usd_per_request` | Decimal \| null | 否 | 单价 |
| `plan_label` | str \| null | 否 | 套餐标签 |
| `valid_from` `valid_until` | datetime \| null | 否 | 生效区间 |
| `enabled` | bool | 否（默认 true） | 是否启用 |

**响应**（`QuotaRuleBatchUpsertResponse`）：
- `succeeded: list[QuotaRuleResponse]`
- `failed: list[{index, error}]`

**配置凭据上游限额示例**：

```bash
curl -X PUT "$BASE/gateway/teams/$TEAM_ID/quota-rules/batch" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "rules": [{
      "layer": "upstream",
      "credential_id": "'"$CRED_ID"'",
      "model_name": "volcengine/gpt-4o",
      "window_seconds": 86400,
      "reset_strategy": "calendar_daily_utc",
      "period_timezone": "Asia/Shanghai",
      "period_reset_minutes": 1020,
      "quota_label": "gpt-4o 日限额",
      "limit_tokens": 4800000,
      "enabled": true
    }]
  }'
```

> **`model_name` 格式（重要）**：必须用**完整 `real_model`**（含 provider 前缀，如 `volcengine/doubao-seedance-1-0-pro-250528`），不要用去掉前缀的纯模型名。生图/生视频类模型（如 doubao-seedance、doubao-seedream 系列）若传不带前缀的名，后端校验"未注册在该凭据下"会失败；普通 chat 模型传不带前缀的名虽能成功（后端自动补全），但为统一规范，**一律传完整 `real_model`**。
>
> **日限额 + 自定义重置时刻**：用 `window_seconds:86400` + `reset_strategy:"calendar_daily_utc"` + `period_timezone:"Asia/Shanghai"` + `period_reset_minutes:<分钟数>`（如下午5点=1020）。不要用 `period:"daily"` 字段，那无法指定重置时刻。

## 成员自助 upsert 上游配额

`PUT /gateway/teams/{team_id}/quota-rules/self-batch`

**认证**：`CurrentTeam`（任意成员，但仅能写本人 BYOK 凭据的上游配额或本人平台配额）。

## 启停与调整用量

| 操作 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 启停单条配额 | `POST` | `/gateway/teams/{team_id}/quota-rules/enablement` | `RequiredTeamAdmin` |
| 成员自助启停 | `POST` | `/gateway/teams/{team_id}/quota-rules/self/enablement` | `CurrentTeam` |
| 手工设置用量/清零窗口 | `POST` | `/gateway/teams/{team_id}/quota-rules/usage-adjustments` | `RequiredTeamAdmin` |
| 成员自助调整用量 | `POST` | `/gateway/teams/{team_id}/quota-rules/self/usage-adjustments` | `CurrentTeam` |

### 请求体

**`QuotaRuleEnablementRequest`**：`layer`、`budget_id`、`plan_id`、`quota_id`、`enabled`

**`QuotaUsageAdjustmentRequest`**：`layer`、`budget_id`、`plan_id`、`quota_id`、`mode`（`set`/`reset_window`）、`current_usd`、`current_tokens`、`current_requests`、`current_images`

## 删除配额

| 操作 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 删除上游/下游配额 | `DELETE` | `/gateway/teams/{team_id}/quota-rules/plan?layer=upstream\|downstream&quota_id=&plan_id=` | `RequiredTeamAdmin` |
| 成员自助删除本人上游配额 | `DELETE` | `/gateway/teams/{team_id}/quota-rules/self/plan?quota_id=&plan_id=` | `CurrentTeam` |
| 成员自助删除本人平台配额 | `DELETE` | `/gateway/teams/{team_id}/quota-rules/self/{budget_id}` | `CurrentTeam` |

## 旧式平台预算端点（简化版）

路由文件：`backend/domains/gateway/presentation/routers/budgets.py`

| 操作 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 列预算 | `GET` | `/gateway/teams/{team_id}/budgets?target_kind=&model_name=` | Admin 全量；成员仅本人 |
| upsert 预算 | `PUT` | `/gateway/teams/{team_id}/budgets` | `BudgetUpsert` |
| 删除预算 | `DELETE` | `/gateway/teams/{team_id}/budgets/{budget_id}` | - |

`BudgetUpsert`：
- `target_kind`（`system`/`tenant`/`key`/`user`）、`target_id`
- `period`（`daily`/`monthly`/`total`）、`model_name`
- `limit_usd`、`soft_limit_usd`、`limit_tokens`、`limit_requests`、`limit_images`
- `period_timezone`、`period_reset_minutes`、`period_reset_day`

`BudgetResponse` 含 `current_usd`/`current_tokens`/`current_requests`/`current_images`/`reset_at`/`budget_reset_at`。

> **注意**：`Budget` 是平台预算（`gateway_budgets` 表），不是上游凭据限额。上游凭据限额通过 `provider_quotas` + `quota-rules` API（`layer=upstream`）配置。

## 下游套餐（Entitlement Plan）

路由文件：`backend/domains/gateway/presentation/routers/plans.py`

| 操作 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 列 vkey 套餐 | `GET` | `/gateway/teams/{team_id}/keys/{vkey_id}/entitlements` | `RequiredTeamAdmin` |
| 创建 vkey 套餐 | `POST` | `/gateway/teams/{team_id}/keys/{vkey_id}/entitlements` | `RequiredTeamAdmin` |
| 更新套餐 | `PATCH` | `/gateway/teams/{team_id}/entitlements/{plan_id}` | `RequiredTeamAdmin` |
| 删除套餐 | `DELETE` | `/gateway/teams/{team_id}/entitlements/{plan_id}` | `RequiredTeamAdmin` |
| 套餐用量 | `GET` | `/gateway/teams/{team_id}/entitlements/{plan_id}/usage` | `RequiredTeamAdmin` |
| apikey_grant 套餐 | `GET`/`POST` | `/gateway/teams/{team_id}/api-key-grants/{grant_id}/entitlements` | `RequiredTeamAdmin` |

Schema：`EntitlementPlanCreate`/`EntitlementPlanResponse`/`EntitlementPlanQuotaUpsert`（`schemas/common.py:1364-1443`）。

## 关键文件

- 路由：`backend/domains/gateway/presentation/routers/quota_rules.py`、`budgets.py`、`plans.py`
- Schema：`backend/domains/gateway/presentation/schemas/common.py`（QuotaRule/Budget/EntitlementPlan）
- ORM：`backend/domains/gateway/infrastructure/models/provider_quota.py`、`budget.py`、`entitlement_plan.py`
