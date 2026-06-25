---
name: ai-gateway-ops
description: 通过调用 HTTP API 管理 AI Gateway 网关的操作技能，涵盖创建团队、创建或管理凭据、探测凭据上游模型、导入模型到团队、查看与修改模型能力、测试模型连通性、删除模型、创建跨团队个人工作区路由、配置与查看上游限额等全流程操作。当用户要求管理 AI 网关、配置模型凭据团队路由配额、探测上游模型、测试模型可用性、设置上游用量限额、跨团队共享模型或路由时使用。触发词包括创建团队、创建凭据、探测模型、导入模型、模型能力、测试模型、删除模型、个人路由、跨团队路由、上游限额、配额、gateway、凭据、虚拟模型。
agent_created: true
---

# AI Gateway Ops

## Overview

通过调用 AI Gateway 的 HTTP API 完成网关资源的全生命周期管理：团队 → 凭据 → 模型 → 路由 → 配额。所有操作基于已部署的 backend 服务（FastAPI），通过 Bearer JWT 认证，前缀为 `/ai-agent/api/v1/gateway`。

## 前置准备

### 1. 确认服务地址与认证

- **Base URL**：默认线上环境 `https://gateway.giimallai.com/ai-agent/api/v1`（可通过环境变量 `GATEWAY_BASE_URL` 覆盖；本地开发可设为 `http://localhost:8000/ai-agent/api/v1`）。
- **认证（两种方式，推荐 API Key）**：
  - **平台 API Key（推荐，长期有效）**：`Authorization: Bearer sk_xxxxxxxx_xxxxxxxxxxxx`。需在设置页创建 API Key 并勾选 `gateway:admin` + `gateway:read` scope（或选 `gateway_full` 分组）。读操作要求 `gateway:read`，写操作要求 `gateway:admin`。API Key 关联的 user 的 RBAC 角色与团队成员关系自动复用。
  - **JWT（兼容，会过期）**：`Authorization: Bearer eyJhbGciOi...`，由 `POST /auth/token`（邮箱+密码）签发。适合前端交互，不适合自动化（默认 1 小时过期）。
- **团队上下文**：团队作用域端点（路径含 `{team_id}`）优先使用路径 team_id，其次读 `X-Team-Id` 头，最后回退到当前用户的 personal team。个人作用域端点（`/my-*`）无需传 team_id。

### 2. 环境变量配置

技能位于用户级目录 `~/.workbuddy/skills/ai-gateway-ops/`，**不依赖任何项目目录**，可在任意工作目录下调用。仅需配置一个环境变量：

| 变量名 | 含义 | 默认值 |
|--------|------|--------|
| `GATEWAY_API_KEY` | 平台 API Key（`sk_` 开头，推荐） | 无 |
| `GATEWAY_TOKEN` | 兼容回退（API Key 或 JWT） | 无 |
| `GATEWAY_BASE_URL` | API 基地址 | `https://gateway.giimallai.com/ai-agent/api/v1`（内置） |

优先级：`GATEWAY_API_KEY` > `GATEWAY_TOKEN`。两者设任一即可。

**获取 API Key**：登录前端 → 设置页 → API Key Tab → 创建，scope 勾选 `gateway:admin` + `gateway:read`（或 `gateway_full` 分组），有效期可选最长 365 天。创建时返回的 `plain_key`（`sk_` 开头）即为本变量值，**仅显示一次**，丢失需重新创建或调 `/reveal` 解密。

**Linux / macOS / Git Bash（当前会话有效）**：

```bash
export GATEWAY_API_KEY="sk_xxxxxxxx_xxxxxxxxxxxx"
# GATEWAY_BASE_URL 已内置线上默认值，无需设置；如需切换本地环境：
# export GATEWAY_BASE_URL="http://localhost:8000/ai-agent/api/v1"
```

**Windows PowerShell（当前会话有效）**：

```powershell
$env:GATEWAY_API_KEY = "sk_xxxxxxxx_xxxxxxxxxxxx"
```

**Windows CMD（当前会话有效）**：

```cmd
set GATEWAY_API_KEY=sk_xxxxxxxx_xxxxxxxxxxxx
```

**持久化（推荐，避免每次重开终端都要设置）**：

- Windows 持久化（PowerShell，用户级，无需管理员）：
  ```powershell
  [Environment]::SetEnvironmentVariable("GATEWAY_API_KEY", "sk_xxxxxxxx_xxxxxxxxxxxx", "User")
  # 重开终端后生效；或当前会话同时设置 $env:GATEWAY_API_KEY 立即使用
  ```
- Git Bash 持久化：写入 `~/.bashrc` 末尾 `export GATEWAY_API_KEY="..."`，然后 `source ~/.bashrc`。

> API Key 不会过期（除非手动撤销或到期），适合自动化运维。如需撤销，在设置页禁用或删除该 API Key。

### 3. 使用封装客户端脚本

`scripts/gateway_client.py` 封装了所有操作的请求构造、认证注入与响应解析，避免反复手写 curl/requests 代码。优先使用它执行操作；需要定制时再读取并修改脚本。

运行方式（需先设置环境变量或通过参数传入 token）：

```bash
# GATEWAY_BASE_URL 已内置线上默认值 https://gateway.giimallai.com/ai-agent/api/v1
# 仅需设置 API Key（设置页创建，勾选 gateway:admin + gateway:read scope）
export GATEWAY_API_KEY="sk_xxxxxxxx_xxxxxxxxxxxx"

# 调用子命令
python scripts/gateway_client.py <command> [options]
# 例如：
python scripts/gateway_client.py teams create --name "我的团队"
python scripts/gateway_client.py credentials probe --team-id <tid> --credential-id <cid>
python scripts/gateway_client.py models list --team-id <tid> --all   # 自动翻页拉全部
python scripts/gateway_client.py models test --team-id <tid> --model-id <mid>
python scripts/gateway_client.py proxy chat --team-id <tid> --model <model> --message "你好"
```

> **全局参数位置**：`--base-url` / `--token` / `--raw` 必须放在 `<category>` **之前**，如 `python gateway_client.py --token sk_xxx teams list`。放在子命令后会报 `unrecognized arguments`。

未携带 token 时，脚本会报错并提示设置 `GATEWAY_API_KEY`。脚本支持 `--help` 查看每个子命令的参数。

> **沙箱/Agent 环境注意**：若在受限沙箱中运行（Bash 无法直接读 Windows 用户级环境变量），需通过 PowerShell 读取注册表获取：`[Environment]::GetEnvironmentVariable("GATEWAY_API_KEY", "User")`，或在调用前 `export GATEWAY_API_KEY="<值>"` 注入到当前 Bash 会话。

## 任务分类

按需加载对应 references 文档以获取完整字段、状态码与示例。以下为各任务的端点速查与关键约束。

### 1. 团队管理 → `references/team_operations.md`

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建团队 | `POST` | `/gateway/teams` |
| 列出团队 | `GET` | `/gateway/teams` |
| 更新团队 | `PATCH` | `/gateway/teams/{team_id}` |
| 删除团队 | `DELETE` | `/gateway/teams/{team_id}` |

- 创建团队恒为 `kind="shared"`，调用者自动成为 `owner`。
- personal team 由系统隐式创建，不可手动创建。
- 删除团队需 `owner` 权限，且不能删 personal team。

### 2. 凭据管理 → `references/credential_operations.md`

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建团队/系统凭据 | `POST` | `/gateway/teams/{team_id}/credentials` |
| 创建个人 BYOK 凭据 | `POST` | `/gateway/my-credentials` |
| 列出凭据 | `GET` | `/gateway/teams/{team_id}/credentials` |
| 凭据详情 | `GET` | `/gateway/teams/{team_id}/credentials/{credential_id}` |
| 探测上游支持的模型 | `POST` | `/gateway/teams/{team_id}/credentials/{credential_id}/probe` |
| 探测个人凭据上游模型 | `POST` | `/gateway/my-credentials/{credential_id}/probe` |
| 更新凭据 | `PATCH` | `/gateway/teams/{team_id}/credentials/{credential_id}` |
| 删除凭据 | `DELETE` | `/gateway/teams/{team_id}/credentials/{credential_id}` |
| 查看上游 Profile | `GET` | `/gateway/provider-profiles` |

- `provider` 必须在允许列表内（团队/系统凭据：openai/anthropic/azure/bedrock/gemini/vertex_ai/dashscope/deepseek/volcengine/zhipuai/moonshot/cohere/mistral/fireworks/together_ai；个人 BYOK 子集见 references）。
- `api_key` 明文入参，服务端 Fernet 加密落库；响应只返回 `api_key_masked`，明文需调 `/reveal`。
- `scope=system` 需平台 admin；探测返回 `already_registered` 标记是否已导入。

### 3. 模型管理 → `references/model_operations.md`

| 操作 | 方法 | 路径 |
|------|------|------|
| 批量导入上游模型到团队 | `POST` | `/gateway/teams/{team_id}/credentials/{credential_id}/batch-import-models` |
| 手动注册单个团队模型 | `POST` | `/gateway/teams/{team_id}/models` |
| 列出团队模型 | `GET` | `/gateway/teams/{team_id}/models` |
| 模型详情 | `GET` | `/gateway/teams/{team_id}/models/{model_id}` |
| 修改模型（含能力位） | `PATCH` | `/gateway/teams/{team_id}/models/{model_id}` |
| 批量重算能力 | `POST` | `/gateway/teams/{team_id}/models/batch-resync-capabilities` |
| 测试模型连通性 | `POST` | `/gateway/teams/{team_id}/models/{model_id}/test` |
| 删除单个模型 | `DELETE` | `/gateway/teams/{team_id}/models/{model_id}` |
| 批量删除模型 | `POST` | `/gateway/teams/{team_id}/models/batch-delete` |
| 跨团队复制模型 | `POST` | `/gateway/models/copy-to-team` |
| 模型预设目录 | `GET` | `/gateway/teams/{team_id}/models/presets` |

- **模型能力**存储在 `GatewayModel.tags`（JSONB），通过 `PATCH` 的 `tags` 字段或 `model_types`/`resync_capabilities` 修改；无独立"能力"端点。能力位含 `supports_vision`/`supports_tools`/`supports_reasoning`/`thinking_param`/`temperature_policy` 等。
- 测试模型**成功与失败均返回 HTTP 200**，由响应 `success` 字段区分；同用户同模型每分钟限 1 次。
- 批量导入单次最多 50 项；批量删除单次最多 200 项。
- 个人模型对应端点在 `/gateway/my-models` 与 `/gateway/my-credentials/{id}/batch-import-models`。

### 4. 个人工作区路由（跨团队）→ `references/route_operations.md`

| 操作 | 方法 | 路径 |
|------|------|------|
| 列出个人路由 | `GET` | `/gateway/my-routes` |
| 创建个人路由 | `POST` | `/gateway/my-routes` |
| 更新个人路由 | `PATCH` | `/gateway/my-routes/{route_id}` |
| 删除个人路由 | `DELETE` | `/gateway/my-routes/{route_id}` |
| 列出可调用模型（跨团队） | `GET` | `/gateway/my-route-callable-models` |
| 团队路由管理 | `*` | `/gateway/teams/{team_id}/routes` |
| vkey 跨团队授权 | `POST` | `/gateway/teams/{team_id}/keys/{key_id}/grants` |
| 路由跨团队共享（owner 发布） | `POST` | `/gateway/my-routes/{route_id}/grants` |
| 共享进团队的路由列表 | `GET` | `/gateway/teams/{team_id}/shared-routes` |

- 个人路由绑定到当前用户的 **personal team**，`primary_models` 用 `route_ref`（如 `slug/alias`）引用其他团队的模型实现跨团队。
  - **⚠️ `alias` 是模型的 `name` 字段，不是 `real_model`**。不同团队导入同一上游模型时 `name` 可能不同（如夜康用 `doubao-seedream-4.0`，祁拟用 `doubao-seedream-4-0-250828`）。
  - 创建/更新路由前务必先 `GET /my-route-callable-models` 确认可用的 route_ref，否则后端返回 400 `未注册或不可引用的模型别名`。
- 通过 `GET /my-route-callable-models` 获取所有可引用模型的 `route_ref` 与 `prefix_dispatchable` 标记。
- 另一种跨团队共享方式：**Virtual Key Grants**（共享 vkey）或 **Route Team Grants**（共享虚拟路由，委派模式：消费方以暴露别名调用，上游凭据归 owner，计费归消费团队）。

### 5. 上游限额与配额 → `references/quota_operations.md`

| 操作 | 方法 | 路径 |
|------|------|------|
| 查看配额规则（含上游） | `GET` | `/gateway/teams/{team_id}/quota-rules?layer=upstream` |
| 批量 upsert 配额规则 | `PUT` | `/gateway/teams/{team_id}/quota-rules/batch` |
| 成员自助 upsert | `PUT` | `/gateway/teams/{team_id}/quota-rules/self-batch` |
| 启停配额 | `POST` | `/gateway/teams/{team_id}/quota-rules/enablement` |
| 调整用量 | `POST` | `/gateway/teams/{team_id}/quota-rules/usage-adjustments` |
| 删除配额 | `DELETE` | `/gateway/teams/{team_id}/quota-rules/plan` |
| 平台预算（旧式） | `*` | `/gateway/teams/{team_id}/budgets` |

- **上游限额** = `layer="upstream"` 的 QuotaRule，落 `provider_quotas` 表，核心字段 `credential_id` + `model_name`（NULL 表示整凭据共享）。
- **`model_name` 格式（重要）**：必须用**完整 `real_model`**（含 provider 前缀，如 `volcengine/doubao-seedance-1-0-pro-250528`）。生图/生视频模型（seedance/seedream）传不带前缀的名会报"未注册在该凭据下"；普通 chat 模型传不带前缀虽能成功（后端自动补全）但不规范。**便捷模式 `--all-models` 自动用 real_model，无需担心**。
- **日限额 + 自定义重置时刻**：用 `window_seconds:86400` + `reset_strategy:"calendar_daily_utc"` + `period_timezone:"Asia/Shanghai"` + `period_reset_minutes:<分钟数>`（如下午5点=1020 或用 `--reset-at 17:00`）。不要用 `period:"daily"` 字段（无法指定重置时刻）。
- **`quota_label` 限制 40 字符**：便捷模式自动用去掉 provider 前缀的简短名 + " 日限额"，超长自动截断。
- **平台预算** = `layer="platform"`，落 `gateway_budgets` 表，按 `target_kind`（system/tenant/key/user）维度。
- **下游套餐** = `layer="downstream"`，绑定 vkey/apikey_grant。三者由 `quota-rules` 统一 facade 暴露。
- 上游限额 upsert 需团队 admin；成员仅能管理本人 BYOK 凭据的上游配额（self-batch）。
- **模型列表分页**：API 默认 `page_size=20`，团队模型超 20 个时需加 `--page-size 100` 或用 `--all` 自动翻页拉全部。

### 6. Virtual Key 与代理调用 → `references/proxy_operations.md`

网关代理端点（`/openai/v1/*`）用 vkey（`sk-gw-` 开头）认证，**不是**管理面的 API Key 或 JWT。

| 操作 | 命令 |
|------|------|
| 智能获取 vkey（同名复用） | `vkeys ensure --team-id <tid> --name <name>` |
| 列出/创建/解密/删除 vkey | `vkeys list/create/reveal/delete` |
| 聊天测试（自动 ensure vkey） | `proxy chat --team-id <tid> --model <model> --message "..."` |
| 生图测试（自动 ensure vkey） | `proxy image --team-id <tid> --model <model> --prompt "..."` |

- **`vkeys ensure`（核心）**：同名 vkey 存在则 reveal 复用，不存在才创建。**不会每次创建新 vkey**。
- **`proxy chat/image`**：自动调用 `ensure` 获取 vkey 明文后调代理端点，无需手动管理 vkey。
- vkey 明文仅在创建和 reveal 时返回；`ensure` 会自动处理 reveal。
- 代理端点：`POST /openai/v1/chat/completions`（聊天）、`POST /openai/v1/images/generations`（生图）。

### 7. 上游模型参考 → `references/volcano_ark_reward_models.md`

火山方舟（Volcano Ark）协作奖励计划提供免费 token 额度，适合内部研发与测试。该文档包含：

- **30 个协作奖励计划模型**完整清单（real_model / capability / model_types / 说明），按 6 类分组（Seed 2.x / Seed 专用 / Seed 1.x / 1.5 / 视觉生成 / 第三方）
- **非协作奖励模型黑名单**（DeepSeek-V4、3D、embedding-vision 等，导入会产生费用）
- **快速操作指南**：创建火山凭据 → 探测上游 → 批量导入协作模型 → 配置日限额（480 万 tokens/天，17:00 重置）→ 清理非协作模型 → 创建分类路由
- **注意事项**：额度重置时间、数据隐私、模型命名差异、计划有效期

> 当用户提到"火山"、"方舟"、"协作奖励"、"volcengine"、"豆包"、"doubao"、"deepseek-v3"、"seedream"、"seedance"等关键词时，先读取该文档获取准确的 real_model 列表与能力分类，再执行导入/配额/路由操作。

## 常见端到端工作流

### 工作流 A：从零搭建一个团队的模型调用能力

1. `POST /gateway/teams` 创建团队，记录 `team_id`。
2. `POST /gateway/teams/{team_id}/credentials` 创建凭据（传 `provider`/`name`/`api_key`），记录 `credential_id`。
3. `POST /gateway/teams/{team_id}/credentials/{credential_id}/probe` 探测上游可用模型，获取 `items[].upstream_model_id`。
4. `POST /gateway/teams/{team_id}/credentials/{credential_id}/batch-import-models` 批量导入选定模型。
5. `POST /gateway/teams/{team_id}/models/{model_id}/test` 测试连通性。
6. （可选）`PUT /gateway/teams/{team_id}/quota-rules/batch` 配置上游限额。
7. （可选）`POST /gateway/teams/{team_id}/routes` 创建团队虚拟路由。

### 工作流 B：跨团队共享模型（个人工作区聚合）

1. 在各团队完成模型注册（工作流 A）。
2. `GET /gateway/my-route-callable-models` 获取所有可引用模型的 `route_ref`。
3. `POST /gateway/my-routes` 创建个人路由，`primary_models` 填入跨团队的 `route_ref`（用 `slug/alias` 形式）。
4. （可选）`POST /gateway/my-routes/{route_id}/grants` 把个人路由发布给协作团队（委派模式，消费方以暴露别名调用）。
5. （可选）`POST /gateway/teams/{team_id}/keys/{key_id}/grants` 把 vkey 授权给其他团队。

### 工作流 C：调整模型能力

1. `GET /gateway/teams/{team_id}/models/{model_id}` 查看当前 `tags` 与 `selector_capabilities`。
2. `PATCH /gateway/teams/{team_id}/models/{model_id}` 修改 `tags`（如 `{"supports_vision": true, "thinking_param": "none"}`），或传 `resync_capabilities: true` 从 LiteLLM 重算。

### 工作流 D：批量清理非目标模型 + 统一配置上游限额

适用场景：团队中混入了不在上游奖励计划/白名单内的模型，需清理并对保留模型统一设日限额。

> 火山方舟协作奖励计划的完整模型清单见 `references/volcano_ark_reward_models.md`，执行前先读取该文档获取准确的 real_model 列表与能力分类。

1. `models list --team-id <tid> --all` 拉取团队全部模型（`--all` 自动翻页，避免分页不全）。
2. 与目标清单（如 `references/volcano_ark_reward_models.md` 中的协作奖励模型表）对比，识别需删除的模型 ID。
3. `models batch-delete --team-id <tid> --model-ids '["id1","id2"]'` 批量删除（单次最多 200 项）。
4. `quotas batch-upsert --team-id <tid> --credential-id <cid> --limit-tokens 4800000 --all-models --reset-at 17:00` **便捷模式**：自动拉取该凭据下全部模型，为每个生成一条上游日限额规则（含重置时刻）。无需手写 N 条 JSON。
5. `quotas list --team-id <tid> --layer upstream --credential-id <cid> --page-size 100` 验证规则数与限额值。

> **便捷模式 vs 显式模式**：便捷模式（`--all-models`）适合"给某凭据下全部模型配统一限额"；显式模式（`--rules '[...]'`）适合"给不同模型配不同限额"。便捷模式自动用完整 `real_model` 作为 `model_name`，避免生图/生视频模型因命名格式不符报错。

### 工作流 E：火山协作奖励计划模型全流程配置

适用场景：新团队接入火山方舟协作奖励计划，从零配置到可用。

> 详细模型清单与说明见 `references/volcano_ark_reward_models.md`。

1. `credentials create --team-id <tid> --provider volcengine --name "火山-团队名" --api-key <ark-api-key>` 创建火山凭据。
2. `credentials probe --team-id <tid> --credential-id <cid>` 探测上游（返回 124+ 个模型，其中 30 个在协作奖励计划内）。
3. `models batch-import --team-id <tid> --credential-id <cid> --provider volcengine --items '[...]'` 批量导入协作奖励模型（items 从 `volcano_ark_reward_models.md` 的 real_model 列去掉 `volcengine/` 前缀构造）。
4. `quotas batch-upsert --team-id <tid> --credential-id <cid> --limit-tokens 4800000 --all-models --reset-at 17:00` 配置日限额（480 万 < 500 万额度上限，17:00 对齐火山重置时间）。
5. （可选）`routes my-create --virtual-model "volcano-text-pool" --primary-models '[...]'` 创建分类路由（纯文本/图片识别/生图/生视频）。

### 工作流 F：测试模型调用（聊天/生图）

通过网关代理端点测试模型是否可用，**自动复用 vkey**，无需手动创建。

```bash
# 聊天测试（自动 ensure vkey "gateway-proxy"，同名复用）
python gateway_client.py proxy chat --team-id <tid> --model <model-name> --message "你好" --max-tokens 80

# 生图测试
python gateway_client.py proxy image --team-id <tid> --model <image-model> --prompt "一只猫" --n 1

# 测试个人路由（路由名作为 model）
python gateway_client.py proxy chat --team-id <tid> --model volcano-text-pool --message "1+1=?"

# 单独获取/复用 vkey 明文（用于 curl 手动调用）
python gateway_client.py vkeys ensure --team-id <tid> --name "gateway-proxy"
```

> `proxy` 命令内部调用 `vkeys ensure`：同名 vkey 存在则 reveal 复用，不存在才创建。**不会每次创建新 vkey**。
> 详细说明见 `references/proxy_operations.md`。

## 错误处理约定

- 业务错误返回统一 JSON：`{"error": {"code": "<CODE>", "message": "...", "details": {...}}}`，HTTP 状态码映射见 `references/api_conventions.md`。
- 常见 code：`UNAUTHORIZED`(401)、`FORBIDDEN`(403)、`NOT_FOUND`(404)、`VALIDATION_ERROR`(422)、`CONFLICT`(409)、`RATE_LIMITED`(429)。
- 探测/测试类操作的失败通常仍返回 200 并在响应体中给出 `message`/`reason`，需检查 `success`/`support` 字段。

## Resources

### scripts/
- `gateway_client.py` — 封装全部操作的 CLI 客户端。按子命令组织（`teams`/`credentials`/`models`/`routes`/`quotas`/`vkeys`/`proxy`），自动注入 `Authorization` 头与 base URL，解析并格式化 JSON 响应。优先用它执行操作；定制需求可直接读取并修改脚本。

### references/
- `api_conventions.md` — 全局约定：路径前缀、认证、RBAC、团队上下文解析、响应格式、错误码。
- `team_operations.md` — 团队 CRUD 与成员管理完整字段。
- `credential_operations.md` — 凭据创建/探测/复制/可见性，含 provider 白名单与 profile 说明。
- `model_operations.md` — 模型导入/查看/能力修改/测试/删除/复制，含能力位清单。
- `route_operations.md` — 个人工作区路由与跨团队引用、vkey grants。
- `quota_operations.md` — 上游限额/平台预算/下游套餐统一 facade。
- `proxy_operations.md` — Virtual Key 管理与网关代理调用（聊天/生图），含 ensure 智能复用与错误排查。
- `volcano_ark_reward_models.md` — 火山方舟协作奖励计划模型参考（30 个协作模型 + 非协作黑名单 + 快速操作指南）。

加载策略：执行某类任务前，先读取对应 references 文档以获取准确字段定义与示例；`api_conventions.md` 在首次使用或遇到认证/权限问题时必读。
