# Virtual Key 与代理调用

网关代理端点（`/openai/v1/*`）用 **Virtual Key (vkey)** 认证，而非管理面的 API Key 或 JWT。vkey 是团队级凭据，绑定到某个团队，调用时该团队下的模型可被路由。

## vkey 生命周期

```
创建 vkey（返回明文，仅一次）→ 明文调用代理端点 → 可 reveal 再次获取明文 → 可删除
```

> **重要**：vkey 明文仅在创建和 reveal 时返回。创建后请保存明文；丢失可用 `reveal` 重新获取。

## 命令速查

| 操作 | 命令 |
|------|------|
| 列出团队 vkey | `vkeys list --team-id <tid>` |
| 创建 vkey | `vkeys create --team-id <tid> --name <name>` |
| 解密明文 | `vkeys reveal --team-id <tid> --key-id <kid>` |
| **智能获取（推荐）** | `vkeys ensure --team-id <tid> --name <name>` |
| 删除 vkey | `vkeys delete --team-id <tid> --key-id <kid>` |
| **聊天测试** | `proxy chat --team-id <tid> --model <model> --message "..."` |
| **生图测试** | `proxy image --team-id <tid> --model <model> --prompt "..."` |
| **列出代理可见模型** | `proxy models --team-id <tid> [--filter volcano]` |

### vkeys ensure —— 智能复用（核心）

`ensure` 是推荐用法，**不会每次创建新 vkey**：

1. 先 `list` 团队已有 vkey
2. 找到同名的 active vkey → `reveal` 返回明文（**复用**）
3. 没找到 → `create` 新建并返回明文

```bash
# 第一次调用：创建名为 gateway-proxy 的 vkey
python gateway_client.py vkeys ensure --team-id <tid> --name "gateway-proxy"
# 输出: {"id": "...", "plain_key": "sk-gw-...", "reused": false}

# 后续调用：复用同名 vkey，不新建
python gateway_client.py vkeys ensure --team-id <tid> --name "gateway-proxy"
# 输出: {"id": "...", "plain_key": "sk-gw-...", "reused": true}
```

### proxy chat —— 聊天测试（自动 ensure vkey）

```bash
# 测试团队模型（自动获取/复用 vkey，无需手动管理）
python gateway_client.py proxy chat \
    --team-id <tid> --model doubao-seed-1-6-250615 \
    --message "你好，一句话介绍你自己" --max-tokens 80

# 测试个人路由（路由名作为 model）
python gateway_client.py proxy chat \
    --team-id <tid> --model volcano-text-pool \
    --message "1+1=?" --max-tokens 20
```

> `--vkey-name` 默认 `gateway-proxy`，同名自动复用。不同用途可用不同名称。

### proxy image —— 生图测试（自动 ensure vkey）

```bash
python gateway_client.py proxy image \
    --team-id <tid> --model doubao-seedream-4-0-250828 \
    --prompt "一只可爱的猫咪" --n 1
```

## 代理端点

| 端点 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 聊天补全 | `POST` | `/openai/v1/chat/completions` | `Authorization: Bearer sk-gw-...` |
| 文生图 | `POST` | `/openai/v1/images/generations` | `Authorization: Bearer sk-gw-...` |
| 模型列表 | `GET` | `/openai/v1/models` | `Authorization: Bearer sk-gw-...` |

> 代理端点用 vkey（`sk-gw-` 开头）认证，**不是**管理面的 API Key（`sk_` 开头）或 JWT。

## vkey 管理 API

| 操作 | 方法 | 路径 |
|------|------|------|
| 列出 vkey | `GET` | `/gateway/teams/{team_id}/keys` |
| 创建 vkey | `POST` | `/gateway/teams/{team_id}/keys` |
| vkey 详情 | `GET` | `/gateway/teams/{team_id}/keys/{key_id}` |
| 解密明文 | `GET` | `/gateway/teams/{team_id}/keys/{key_id}/reveal` |
| 删除 vkey | `DELETE` | `/gateway/teams/{team_id}/keys/{key_id}` |
| 跨团队授权 | `POST` | `/gateway/teams/{team_id}/keys/{key_id}/grants` |

## 常见错误排查

| 错误 | 原因 | 解决 |
|------|------|------|
| `model_not_found: 未找到已注册的 Gateway 模型` | model 名不存在于该团队 | 检查 model 名是否在 `models list` 中 |
| `model_not_found: has not activated the model` | 上游账户未激活该模型 | 到火山控制台开通模型服务 |
| `permission_error: overdue balance` | 上游账户欠费 | 到火山控制台充值 |
| `invalid_request: requires credential extra.image_endpoint_id` | 凭据缺生图接入点 | PATCH 凭据 extra 补充 `image_endpoint_id` |
| `401 Unauthorized` | vkey 无效或已删除 | 用 `ensure` 重新获取 |

## 手动调用（不用脚本）

```bash
# 1. 获取 vkey 明文
VKEY=$(python gateway_client.py vkeys ensure --team-id <tid> --name "test" --raw | python -c "import sys,json;print(json.load(sys.stdin)['plain_key'])")

# 2. 调用代理端点
curl -X POST "http://localhost:8000/ai-agent/api/v1/openai/v1/chat/completions" \
    -H "Authorization: Bearer $VKEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"doubao-seed-1-6-250615","messages":[{"role":"user","content":"你好"}]}'
```
