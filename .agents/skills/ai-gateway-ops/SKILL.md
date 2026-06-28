---
name: ai-gateway-ops
description: 通过 HTTP API 与 gateway_client.py CLI 管理 AI Gateway（团队、凭据、模型、路由共享、配额、vkey、代理调用、日志归因）。当用户要求管理 AI 网关、配置凭据/模型/路由/配额、跨团队共享路由、探测上游、测试调用或核对用量归因时使用。触发词：gateway、凭据、模型、路由、共享、配额、vkey、代理调用、日志、归因。
---

# AI Gateway Ops

## Agent 执行约束（必读）

1. **只用 `scripts/gateway_client.py`** 执行操作；禁止为常规任务临时写 Python/curl（易错：reveal 用 GET、全局参数位置、错误体嵌套）。
2. **脚本路径**：项目技能目录 `.agents/skills/ai-gateway-ops/scripts/gateway_client.py`（相对仓库根目录）。
3. **全局参数** `--base-url` / `--token` / `--raw` 必须放在 `<category>` **之前**。
4. **先查再改**：团队用 `teams find`；路由引用用 `routes my-callable-models`；共享结果用 `routes shared-routes-list`。
5. **认证分工**：管理面 `GATEWAY_API_KEY`（`sk_`）；代理 `sk-gw-` vkey（`proxy` / `vkeys ensure` 自动处理）。
6. **Windows**：PowerShell 用 `;` 链接命令（不用 `&&`）；读用户级 Key：`[Environment]::GetEnvironmentVariable("GATEWAY_API_KEY", "User")`。
7. **故障**：先读 [references/troubleshooting.md](references/troubleshooting.md)。

## 快速开始

```bash
# 环境（线上默认已内置 GATEWAY_BASE_URL）
export GATEWAY_API_KEY="sk_xxxxxxxx_xxxxxxxxxxxx"

# 脚本入口（仓库内）
python .agents/skills/ai-gateway-ops/scripts/gateway_client.py <category> <command> [options]

# 示例
python .agents/skills/ai-gateway-ops/scripts/gateway_client.py auth whoami
python .agents/skills/ai-gateway-ops/scripts/gateway_client.py teams find --name-contains "研发API"
python .agents/skills/ai-gateway-ops/scripts/gateway_client.py routes my-list
python .agents/skills/ai-gateway-ops/scripts/gateway_client.py proxy chat --team-id <tid> --model volcano-text-pool --message "hi"
```

| 变量 | 含义 | 默认 |
|------|------|------|
| `GATEWAY_API_KEY` | 平台 API Key（`sk_`，需 `gateway:admin`+`gateway:read`） | 无 |
| `GATEWAY_TOKEN` | 兼容 JWT/Key 回退 | 无 |
| `GATEWAY_BASE_URL` | API 基地址 | `https://gateway.giimallai.com/ai-agent/api/v1` |
| `GATEWAY_PROXY_VKEY` | 代理面 vkey（`sk-gw-`，批量测试脚本优先使用，免每次 ensure） | 无 |
| `GATEWAY_BATCH_TEAM_ID` | 批量测试默认团队 ID（`batch_call_pools.py` 的 `--team-id` 缺省） | 无 |
| `GATEWAY_DB_DSN` | `query_route_models.py` 只读查库 DSN | 生产 ai_agent 库 |

API Key：设置页 → API Key → 创建 → 勾选 `gateway_full` 或 `gateway:admin`+`gateway:read`。

**Windows 持久化**（用户级，重启/新终端生效）：`setx GATEWAY_API_KEY "sk_..."`；读取：`[Environment]::GetEnvironmentVariable("GATEWAY_API_KEY","User")`。

## CLI 命令速查

| 类别 | 常用命令 |
|------|----------|
| **auth** | `whoami` |
| **teams** | `list` · `find --name-contains` · `create` |
| **credentials** | `list` · `create` · `probe` |
| **models** | `list --all` · `capabilities` · `get` · `update --resync-capabilities` · `update --context-window` · `resync` · `test` · `batch-import` · `batch-delete` |
| **routes** | `my-list` · `my-create` · `my-callable-models` |
| **routes 共享** | `route-grants-publish --all-routes` · `route-grants-create` · `shared-routes-list` · `route-grants-list` |
| **routes vkey** | `grants-create`（vkey 跨团队，非路由共享） |
| **vkeys** | `ensure` · `list` · `reveal` |
| **proxy** | `chat` · `image` · `models [--filter]` |
| **logs** | `list` · `get --attribution-only` |
| **stats** | `summary --group-by user` |
| **quotas** | `list` · `batch-upsert --all-models` |

完整参数：`python gateway_client.py <category> --help`。

## 任务与 references

| 任务 | 文档 |
|------|------|
| 团队/成员 | [team_operations.md](references/team_operations.md) |
| 凭据/探测 | [credential_operations.md](references/credential_operations.md) |
| 模型/能力 | [model_operations.md](references/model_operations.md) |
| 路由/共享/归因 | [route_operations.md](references/route_operations.md) |
| 配额/限额 | [quota_operations.md](references/quota_operations.md) |
| vkey/代理 | [proxy_operations.md](references/proxy_operations.md) |
| 火山协作模型 | [volcano_ark_reward_models.md](references/volcano_ark_reward_models.md) |
| 故障排查 | [troubleshooting.md](references/troubleshooting.md) |
| API 约定 | [api_conventions.md](references/api_conventions.md) |

## 路由跨团队共享（Route Team Grants）

**委派模式**：消费方以 `exposed_alias` 调用；上游凭据按 **路由 owner** 解析。

**用量归因（多维，非互斥）**：

| 维度 | 字段 | 含义 |
|------|------|------|
| 消费团队 | `team_id` | 平台预算/团队切片计费 |
| 调用人 | `user_id` | 每条请求记实际调用者 |
| 资源提供方 | `route_snapshot.owner_user_id` | 谁共享了这条路由 |

> 说「计费归消费团队」指 **团队预算层**；不等于不记调用人。配置了 per-user 预算时也会按人扣减。

**CLI 示例**（把全部个人路由发布到研发团队）：

```bash
python gateway_client.py teams find --name-contains "研发API"   # 记下 id
python gateway_client.py routes route-grants-publish --target-team-id <tid> --all-routes
python gateway_client.py routes shared-routes-list --team-id <tid>
```

## 常见工作流

### A：从零搭建团队模型能力

`teams create` → `credentials create` → `credentials probe` → `models batch-import` → `models test` →（可选）`quotas batch-upsert`

### B：个人路由跨团队聚合

`routes my-callable-models` → `routes my-create` →（可选）`routes route-grants-publish`

### C：调整模型能力（含 context_window）

```bash
# 查看当前能力
python gateway_client.py models capabilities --team-id <tid> --model-id <mid>

# 从 LiteLLM 同步（supports_* + context_window）
python gateway_client.py models update --team-id <tid> --model-id <mid> --resync-capabilities

# 手动补充 / 清除上下文窗口
python gateway_client.py models update --team-id <tid> --model-id <mid> --context-window 262144
python gateway_client.py models update --team-id <tid> --model-id <mid> --context-window 0

# 批量同步（导入后缺 context_window 时）
python gateway_client.py models list --team-id <tid> --all --capabilities   # 审计
python gateway_client.py models resync --team-id <tid> --model-ids '["uuid1","uuid2"]'
```

也可用 `models update --tags '{"supports_vision":true}'` 逐项修改；详见 [model_operations.md](references/model_operations.md)。

### D：批量清理 + 上游日限额

`models list --all` → 对照 [volcano_ark_reward_models.md](references/volcano_ark_reward_models.md) → `models batch-delete` → `quotas batch-upsert --all-models --reset-at 17:00`

### E：火山协作奖励全流程

见 [volcano_ark_reward_models.md](references/volcano_ark_reward_models.md) 与 SKILL 内工作流 D/E 细节（`credentials`→`probe`→`batch-import`→`quotas`→`routes my-create`）。

### F：代理测试

```bash
python gateway_client.py proxy chat --team-id <tid> --model <name> --message "你好"
python gateway_client.py proxy models --team-id <tid> --filter volcano
```

### G：共享路由调用 + 归因验证

```bash
# 1. 确认消费团队可见别名
python gateway_client.py proxy models --team-id <consumer_tid> --filter <alias>

# 2. 调用（自动 ensure vkey）
python gateway_client.py proxy chat --team-id <consumer_tid> --model <alias> --message "归因测试" --max-tokens 20

# 3. 查日志（团队切片 + 按模型过滤）
python gateway_client.py logs list --team-id <consumer_tid> --model <alias> --page-size 5

# 4. 详情看委派归因
python gateway_client.py logs get --team-id <consumer_tid> --log-id <id> --attribution-only

# 5. 按人聚合（可选）
python gateway_client.py stats summary --team-id <consumer_tid> --group-by user --start 2026-06-25T00:00:00Z
```

期望：`team_id`=消费团队、`user_id`=调用人、`route_snapshot.delegated=true`、`owner_user_id`=路由 owner。

### H：路由 Pool 批量调用测试 + 配置审计

**背景**：火山 `volcano-text-pool` / `volcano-vision-pool` 是多 deployment 路由别名，需验证池内模型可用性与配置正确性。阿里云 ALB 有 60s 空闲超时，长请求须用流式（`--stream`）规避 504。

```bash
# 0. 环境变量齐全时（GATEWAY_PROXY_VKEY / GATEWAY_BATCH_TEAM_ID 已 setx），直接跑：
python .agents/skills/ai-gateway-ops/scripts/batch_call_pools.py --stream

# 1. 用本地图片测视觉池（规避外网拉图超时）
python .agents/skills/ai-gateway-ops/scripts/batch_call_pools.py --stream --image-file scripts/面向接口.jpg

# 2. 逐模型测试（绕过路由别名，直接打每个底层模型，验证全部 deployment）
python .agents/skills/ai-gateway-ops/scripts/batch_call_pools.py --stream \
  --models doubao-1-5-pro-32k-250115,doubao-seed-1-6-vision-250815

# 3. 路由配置审计（数据库 SSOT，关联 gateway_models 显示 enabled 状态）
python .agents/skills/ai-gateway-ops/scripts/query_route_models.py

# 4. 重复配置检测（CI 友好，发现重复返回非零退出码）
python .agents/skills/ai-gateway-ops/scripts/query_route_models.py --check-dups
```

**关键经验**：
- **不要用日志反推路由配置**：日志只能证明"被调用过"，不能证明"配置了但没被调用"。数据库 `gateway_routes.primary_models` 才是 SSOT。
- **重复配置后果**：`primary_models` 中同一 `team-xxx/model` 出现多次，会注册成多个 deployment，导致权重翻倍。`--check-dups` 可在 CI 中守门。
- **改库后必须热重载**：路由单例是进程级内存缓存，直接改库不重载 = 配置与内存不一致。正道是管理 API（`PATCH /routes/{id}` 自动 `reload_router` + Redis pub/sub 通知所有 worker）；无 admin token 时用 `kubectl rollout restart` 兜底。
- **brotli 解码 bug**：httpx 流式 + brotli 压缩会报 `decoder process called with data when 'can_accept_more_data()' is False`，脚本已用 `Accept-Encoding: gzip` 规避。

## 错误处理

- 管理面：`{"error": {"code", "message", "details"}}`
- 代理面：可能为 `{"detail": {"error": {...}}}`（CLI 已解析）
- 探测/测试：HTTP 200 时仍查 `success` 字段

## Resources

- `scripts/gateway_client.py` — **唯一推荐执行入口**（teams/credentials/models/routes/quotas/vkeys/proxy/logs/stats/auth）
- `scripts/batch_call_pools.py` — 路由 Pool 批量调用测试（流式规避 ALB 504，支持本地图片/逐模型/路由别名模式）
- `scripts/query_route_models.py` — 路由配置审计（查 `gateway_routes` + 关联 `gateway_models` 状态，含 `--check-dups` 重复检测）
- `references/*` — 字段与端点详情；执行前按需加载
