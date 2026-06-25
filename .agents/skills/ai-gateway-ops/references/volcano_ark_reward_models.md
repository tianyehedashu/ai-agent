# 火山方舟协作奖励计划模型参考

> 火山方舟（Volcano Ark）协作奖励计划为接入方提供免费 token 额度，适合内部研发与测试场景。
> 本文档列出全部协作奖励计划模型，便于按需导入团队与配置上游限额。

## 计划概览

- **官方文档**：https://www.volcengine.com/docs/82379/1391869
- **控制台入口**：火山方舟控制台 → 开通管理 → 协作奖励计划
- **API Endpoint**：`https://ark.cn-beijing.volces.com/api/v3`（OpenAI 兼容）
- **免费额度**：
  - 个人用户：每款模型每天 50 万 tokens
  - 企业用户：单模型每天最高 500 万 tokens
- **数据说明**：调用数据会被加密和匿名化处理，适合不介意数据隐私的场景
- **provider 标识**：`volcengine`
- **凭据创建**：在 Gateway 用 `provider=volcengine` 创建凭据，`api_key` 填火山控制台的 API Key

## ⚠️ 关键注意事项

1. **以控制台页面为准**：火山奖励计划页面（`/openManagement/rewardPlan`）实际授权的模型列表才是准确的。API `ListDataCollectionPermissions` 返回 66 个模型（含所有厂商全量），其中只有 39 个是协作奖励计划模型。
2. **模型命名差异**：火山 FoundationModelName 用连字符（`doubao-1-5-vision-pro`），但上游模型 ID 可能用点号（`doubao-1.5-vision-pro`）或带版本后缀（`doubao-1-5-vision-pro-32k-250115`）。导入时用 `upstream_model_id`（含版本后缀）。
3. **route_ref 用 name 字段**：路由 `primary_models` 中的引用格式是 `team-slug/{model.name}`，**不是** `real_model`。不同团队导入同一上游模型时 `name` 可能不同（一个用点号、一个用版本号），创建路由前务必先 `GET /my-route-callable-models` 确认可用的 route_ref。
4. **API 授权失效**：`CreateDataCollectionPermission` API 对所有模型返回 `OperationDenied.activities has ended`，实际授权需通过 UI 流程（ziniao-cli 浏览器自动化）。

## 协作奖励计划模型清单（39 个）

以下 39 个模型为火山控制台协作奖励计划页面实际授权的模型（FoundationModelName）：

| # | FoundationModelName | DisplayName | 类别 |
|---|---------------------|-------------|------|
| 1 | doubao-seed-evolving | Doubao-Seed-Evolving | Agent/Coding 持续进化 |
| 2 | doubao-seed-2-1-pro | Doubao-Seed-2.1-pro | 旗舰 pro |
| 3 | doubao-seed-2-1-turbo | Doubao-Seed-2.1-turbo | 旗舰 turbo |
| 4 | doubao-seed-2-0-pro | Doubao-Seed-2.0-pro | 2.0 pro |
| 5 | doubao-seed-2-0-mini | Doubao-Seed-2.0-mini | 2.0 mini |
| 6 | doubao-seed-2-0-lite | Doubao-Seed-2.0-lite | 2.0 lite |
| 7 | doubao-seed-2-0-code | Doubao-Seed-2.0-Code | 2.0 代码 |
| 8 | doubao-seed-character | Doubao-Seed-Character | 角色扮演 |
| 9 | doubao-seed-code | Doubao-Seed-Code | 代码模型 |
| 10 | doubao-seed-translation | Doubao-Seed-Translation | 翻译模型 |
| 11 | doubao-seed-1-8 | Doubao-Seed-1.8 | 1.8 |
| 12 | doubao-seed-1-6 | Doubao-Seed-1.6 | 1.6 |
| 13 | doubao-seed-1-6-lite | Doubao-Seed-1.6-lite | 1.6 lite |
| 14 | doubao-seed-1-6-thinking | Doubao-Seed-1.6-thinking | 1.6 思考 |
| 15 | doubao-seed-1-6-flash | Doubao-Seed-1.6-flash | 1.6 flash |
| 16 | doubao-seed-1-6-vision | Doubao-Seed-1.6-vision | 1.6 视觉 |
| 17 | doubao-1-5-pro-32k | Doubao-1.5-pro-32k | 1.5 pro |
| 18 | doubao-1-5-pro-256k | Doubao-1.5-pro-256k | 1.5 pro 256k |
| 19 | doubao-1-5-lite-32k | Doubao-1.5-lite-32k | 1.5 lite |
| 20 | doubao-1-5-vision-pro | Doubao-1.5-vision-pro | 1.5 视觉 pro |
| 21 | doubao-1-5-vision-lite | Doubao-1.5-vision-lite | 1.5 视觉 lite |
| 22 | doubao-1-5-vision-pro-32k | Doubao-1.5-vision-pro-32k | 1.5 视觉 pro 32k |
| 23 | doubao-1-5-thinking-pro | Doubao-1.5-thinking-pro | 1.5 思考 pro |
| 24 | doubao-1-5-ui-tars | Doubao-1.5-UI-TARS | UI 自动化 |
| 25 | doubao-pro-32k | Doubao-pro-32k | 旧版 pro 32k |
| 26 | doubao-pro-128k | Doubao-pro-128k | 旧版 pro 128k |
| 27 | doubao-pro-256k | Doubao-pro-256k | 旧版 pro 256k |
| 28 | doubao-lite-32k | Doubao-lite-32k | 旧版 lite 32k |
| 29 | doubao-lite-128k | Doubao-lite-128k | 旧版 lite 128k |
| 30 | doubao-vision-pro-32k | Doubao-vision-pro-32k | 旧版视觉 pro |
| 31 | doubao-vision-lite-32k | Doubao-vision-lite-32k | 旧版视觉 lite |
| 32 | doubao-seedance-1-5-pro | Doubao-Seedance-1.5-pro | 文生视频 |
| 33 | doubao-seedance-1-0-pro | Doubao-Seedance-1.0-pro | 文生视频 |
| 34 | doubao-seedance-1-0-lite-t2v | Doubao-Seedance-1.0-lite-t2v | 文生视频 lite |
| 35 | doubao-seedance-1-0-lite-i2v | Doubao-Seedance-1.0-lite-i2v | 图生视频 lite |
| 36 | doubao-seedream-5-0 | Doubao-Seedream-5.0-lite | 文生图 5.0 |
| 37 | doubao-seedream-4-5 | Doubao-Seedream-4.5 | 文生图 4.5 |
| 38 | doubao-seedream-4-0 | Doubao-Seedream-4.0 | 文生图 4.0 |
| 39 | doubao-smart-router | Doubao-Smart-Router | 智能路由 |

> **注意**：上表为 FoundationModelName（无版本后缀）。实际导入网关时需用带版本后缀的 `upstream_model_id`（如 `doubao-seed-2-1-pro-260628`），通过 `credentials probe` 获取可用版本。

## 非协作奖励计划模型（不享免费额度，谨慎导入）

以下模型虽在火山上游可用，但**不在协作奖励计划内**，调用会产生费用：

| 模型名 | 说明 |
|--------|------|
| deepseek-v3-2 | DeepSeek V3.2 |
| deepseek-v3-1 | DeepSeek V3.1 |
| deepseek-v3 | DeepSeek V3 |
| deepseek-v4-pro | DeepSeek V4 Pro |
| deepseek-v4-flash | DeepSeek V4 Flash |
| deepseek-r1 | DeepSeek R1 |
| deepseek-r1-distill-qwen-32b | DeepSeek R1 蒸馏 32B |
| deepseek-r1-distill-qwen-7b | DeepSeek R1 蒸馏 7B |
| kimi-k2 | Kimi K2 |
| glm-4-7 | GLM-4.7（智谱） |
| doubao-1-5-pro-32k-character | 1.5 pro 角色版 |
| doubao-1-5-thinking-vision-pro | 1.5 思考视觉 pro |
| doubao-seaweed | 视频生成 Seaweed |
| doubao-seed3d-1-0 | 3D 生成 1.0 |
| doubao-seed3d-2-0 | 3D 生成 2.0 |
| hyper3d-gen2 | 3D 生成 |
| hitem3d-2-0 | 3D 模型 |
| doubao-seedance-2-0 | Seedance 2.0 |
| doubao-seedance-2-0-fast | Seedance 2.0 fast |
| doubao-seedance-2-0-mini | Seedance 2.0 mini |
| doubao-seedance-1-0-pro-fast | Seedance pro fast |
| doubao-seededit-3-0-i2i | 图生图编辑 |
| doubao-seedream-3-0-t2i | 文生图 3.0 |
| wan2-1-14b | Wan2.1 视频生成 |
| doubao-embedding-large | 向量 embedding |
| doubao-embedding-vision | 视觉向量 |
| doubao-pro-4k | 旧版 pro 4k |
| doubao-lite-4k | 旧版 lite 4k |

> 导入团队前请确认是否在协作奖励计划内，避免误用产生费用。判定方法：对照上表，或查看火山控制台协作奖励计划页面。

## 快速操作指南

### 1. 创建火山凭据

```bash
gateway_client.py credentials create \
    --team-id <tid> --provider volcengine --name "火山-团队名" --api-key <ark-api-key>
```

### 2. 探测上游可用模型

```bash
gateway_client.py credentials probe --team-id <tid> --credential-id <cid>
# 返回 124+ 个上游模型，其中 39 个在协作奖励计划内
```

### 3. 批量导入协作奖励模型

用 `batch-import` 传入协作奖励模型的 `upstream_model_id`（即去掉 `volcengine/` 前缀的 real_model）：

```bash
# 先探测可用模型，找到 39 个奖励计划模型的最新版本
gateway_client.py credentials probe --team-id <tid> --credential-id <cid> -o probe.json

# 从 probe 结果中筛选出 39 个 FoundationModelName 对应的最新版本
# 构造 items
ITEMS='[{"upstream_model_id":"doubao-seed-2-1-pro-260628"},{"upstream_model_id":"doubao-seed-2-1-turbo-260628"},...]'

gateway_client.py models batch-import \
    --team-id <tid> --credential-id <cid> --provider volcengine --items "$ITEMS"
```

> **重要**：`upstream_model_id` 必须用带版本后缀的完整 ID（如 `doubao-seed-2-1-pro-260628`），不能用 FoundationModelName（如 `doubao-seed-2-1-pro`）。版本后缀通过 `probe` 获取。
>
> `batch-import` 是幂等的：已注册的模型返回 `failed: "已注册"` 但不影响其他模型导入。

### 4. 配置上游日限额（协作奖励计划额度内）

协作奖励计划企业用户每天每模型最高 500 万 tokens。为避免超额产生费用，建议配置日限额：

```bash
# 便捷模式：为凭据下全部模型配置每日 480 万 tokens 限额，17:00 重置
gateway_client.py quotas batch-upsert \
    --team-id <tid> --credential-id <cid> \
    --limit-tokens 4800000 --all-models --reset-at 17:00
```

> 480 万 < 500 万，留 20 万余量避免边界超限。重置时刻 17:00 对应火山额度重置时间（北京时间下午5点）。

### 5. 清理非协作奖励模型

若团队误导入了非协作奖励模型，批量删除：

```bash
# 先查全部模型
gateway_client.py models list --team-id <tid> --all

# 对照"非协作奖励"表，收集要删除的 model_id
gateway_client.py models delete --team-id <tid> --model-id <mid>
```

### 6. 创建分类路由（可选）

按用途创建个人路由聚合多团队模型：

| 路由名 | 筛选标准 | 用途 |
|--------|----------|------|
| `volcano-text-pool` | `model_types` 含 `text` 且不含 `image` | 纯文本对话 |
| `volcano-vision-pool` | `model_types` 含 `image`（text+image） | 图片识别 |
| `volcano-image-gen-pool` | `capability=image` 且 `model_types` 含 `image_gen` | 文生图 |

```bash
# 先获取可引用模型列表（确认 route_ref 格式）
gateway_client.py routes my-callable-models -o callable.json

# 创建路由（primary_models 用 route_ref = team-slug/model.name）
gateway_client.py routes my-create \
    --virtual-model "volcano-text-pool" \
    --primary-models '["team-slug/model-name",...]'
```

> **route_ref 格式关键**：`primary_models` 中的引用是 `team-slug/{model.name}`，**不是** `real_model`。不同团队导入同一上游模型时 `name` 可能不同（如夜康用 `doubao-seedream-4.0`，祁拟用 `doubao-seedream-4-0-250828`）。务必先 `GET /my-route-callable-models` 确认可用 route_ref。

## 注意事项

- **额度重置**：火山协作奖励计划额度按北京时间每天 17:00 重置，配置上游限额时用 `--reset-at 17:00` 对齐
- **数据隐私**：协作奖励计划会加密匿名化处理调用数据，不适合敏感数据场景
- **模型命名差异**：
  - FoundationModelName 用连字符（`doubao-1-5-vision-pro`）
  - 上游模型 ID 可能用点号（`doubao-1.5-vision-pro`）或带版本（`doubao-1-5-vision-pro-32k-250115`）
  - 网关 `name` 字段可能用点号或版本号，取决于导入方式
  - 路由 route_ref 用 `name` 字段，非 `real_model`
- **生图/生视频模型**：导入后 `model_name`（配额规则中）必须用完整 `real_model`（含 `volcengine/` 前缀）配置配额，否则报"未注册在该凭据下"
- **计划有效期**：关注火山官方公告，计划可能调整或到期，到期后调用会产生费用
- **生图凭据**：部分凭据需额外配置 `image_endpoint_id`（在凭据 extra 字段中），否则生图模型测试会失败
