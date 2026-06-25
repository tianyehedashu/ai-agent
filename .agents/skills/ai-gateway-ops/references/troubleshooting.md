# AI Gateway Ops 故障排查

## 认证与脚本

| 现象 | 原因 | 处理 |
|------|------|------|
| `未设置 GATEWAY_API_KEY` | 环境变量未注入 | PowerShell：`$env:GATEWAY_API_KEY = "sk_..."`；或 `--token sk_...` 放在 **category 之前** |
| Windows 沙箱读不到用户级环境变量 | Bash 子进程隔离 | `[Environment]::GetEnvironmentVariable("GATEWAY_API_KEY", "User")` 后注入当前会话 |
| `unrecognized arguments: --token` | 全局参数位置错误 | `python gateway_client.py --token sk_xxx teams list`（非 `teams list --token`） |
| vkey reveal 405 | 误用 POST | 管理面 reveal 为 **GET**；用 `vkeys reveal` 或 `vkeys ensure` |

## 代理调用（proxy）

| 现象 | 原因 | 处理 |
|------|------|------|
| 403 + `VolcengineException overdue balance` | 上游火山账户欠费 | 充值/换凭据；非网关权限问题。`proxy models` 仍可见路由 |
| 403 无详情 | OpenAI 兼容层嵌套 `detail.error` | 已内置解析；仍无详情时用 `proxy chat` 看 stderr 原始响应 |
| 调用成功但 logs 查不到 | 上游极早失败或采样 | 查 `logs list --status failed`；成功调用默认有采样率 |
| 混淆 API Key 与 vkey | 认证体系不同 | 管理面 `sk_`；代理 `sk-gw-`（`proxy`/`vkeys ensure` 自动处理） |

## 路由与共享

| 现象 | 原因 | 处理 |
|------|------|------|
| 400 未注册或不可引用的模型别名 | `primary_models` 用了 `real_model` 而非 `name` | 先 `routes my-callable-models`，用 `route_ref` |
| 共享后消费团队调不通 | 上游凭据/owner 失权 | 委派走 owner 凭据；owner 失权则 fail-closed |
| 404 `model_not_found` 无可用部署，但单模型 `proxy chat` 正常 | LiteLLM Router 未装配虚拟路由 deployment（常见于 `primary_models` 含 `team-xxx/model` 跨团队引用时增量装配未解析 slug） | 修复后需部署并 `routes my-update` 或滚动重启 Gateway Pod 触发 `reload_router`；临时可用单模型名直连 |
| 重复发布 grant | 同 (route, team) 仅一行 active | 用 `route-grants-publish`（自动跳过已授权） |

## 用量归因（Route Team Grants）

一次调用同时落多维度（非互斥）：

- `team_id`：消费团队 → 平台预算/团队切片
- `user_id`：实际调用人 → `usage_aggregation=user` 或 `stats summary --group-by user`
- `route_snapshot.owner_user_id`：路由资源提供方（详情 `logs get --attribution-only`）

验证委派归因标准流程见 SKILL.md **工作流 G**。

## 分页与列表

| 现象 | 处理 |
|------|------|
| 模型/配额条数不全 | `models list --all` 或 `--page-size 100` |
| 团队名称难找 | `teams find --name-contains "关键词"` |
