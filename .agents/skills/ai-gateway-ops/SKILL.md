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

API Key：设置页 → API Key → 创建 → 勾选 `gateway_full` 或 `gateway:admin`+`gateway:read`。

## CLI 命令速查

| 类别 | 常用命令 |
|------|----------|
| **auth** | `whoami` |
| **teams** | `list` · `find --name-contains` · `create` |
| **credentials** | `list` · `create` · `probe` |
| **models** | `list --all` · `test` · `batch-import` · `batch-delete` |
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

### C：调整模型能力

`models get` → `models update`（`tags` 或 `resync_capabilities`）

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

## 错误处理

- 管理面：`{"error": {"code", "message", "details"}}`
- 代理面：可能为 `{"detail": {"error": {...}}}`（CLI 已解析）
- 探测/测试：HTTP 200 时仍查 `success` 字段

## Resources

- `scripts/gateway_client.py` — **唯一推荐执行入口**（teams/credentials/models/routes/quotas/vkeys/proxy/logs/stats/auth）
- `references/*` — 字段与端点详情；执行前按需加载
