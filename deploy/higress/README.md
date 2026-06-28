# HiGress 接入 AI Agent（SSO + 路由）

公网示例：`https://gateway.giimallai.com/ai-agent/`

**完整 SSO 说明**：[docs/SSO.md](../../docs/SSO.md)

---

## 流量路径

```
gateway.giimallai.com
    │
    ├─ ALB (higress-gateway-ingress) → higress-gateway-cluster
    │
    ├─ /ai-agent/api/*   → Ingress ai-agent-api → backend:8000（rewrite，不经 frontend）
    │                         ↑ giikin-auth-bridge WasmPlugin（SSO Header）
    │
    └─ /ai-agent/*       → Ingress ai-agent-spa → frontend:80（SPA + 静态资源）
```

| 检查项 | 期望 |
|--------|------|
| `GET /ai-agent/api/v1/system/health` | 200 |
| `GET /ai-agent/api/v1/auth/me` 无 Cookie | 401 |
| `GET /ai-agent/api/v1/auth/me` 有 guard_token + auth-bridge | 200 |
| `GET /ai-agent/` | 200 SPA |

---

## 必配项

### 1. Ingress 路由

**API（Gateway / OpenAI 兼容面）** — [`ai-agent-api-ingress.example.yaml`](ai-agent-api-ingress.example.yaml)

- 路由名 **`ai-agent-api`**，`path: /ai-agent/api/` + `pathType: Prefix` → `ai-agent-backend.dns:8000`
- **必须** `higress.io/timeout: "3600"`（缺省约 **60s**，非流式 chat 高并发会 **504**）
- **必须** 用标准 Prefix，**禁止** `use-regex: "true"` + `/ai-agent/api/(.*)`（见下方「504 根因」）
- **禁止** `rewrite-target`：backend `ROOT_PATH=/ai-agent` 需接收带前缀路径，去前缀会 404

> **504 根因（2026-06-27 排查）**：`use-regex: "true"` 的正则路径不参与 K8s 最长前缀优先排序，导致所有 `/ai-agent/api/*` 错误打到 `ai-agent-spa`（frontend Nginx 二次反代），SPA Ingress 默认 timeout 60s → LLM 长请求 504。修复：改标准 Prefix `/ai-agent/api/`（比 `/ai-agent` 更长，自动优先），并删 `use-regex`/`rewrite-target`/`enable-rewrite` 三个 annotation。

线上补丁（已验证）：

```bash
# 修复路由优先级（治本）：apply 标准 Prefix 配置 + 删废弃 annotation
scp deploy/higress/ai-agent-api-ingress.example.yaml wuhan-ali:/tmp/
ssh wuhan-ali "kubectl -n test apply -f /tmp/ai-agent-api-ingress.example.yaml"
ssh wuhan-ali "kubectl -n test annotate ingress ai-agent-api higress.io/use-regex- higress.io/rewrite-target- higress.io/enable-rewrite-"

# SPA 兜底加 timeout（防 LLM 经 Nginx 反代超时）
ssh wuhan-ali "kubectl -n test patch ingress ai-agent-spa --type=merge --patch '{\"metadata\":{\"annotations\":{\"higress.io/timeout\":\"3600\"}}}'"

# 验证：API 请求应打到 ai-agent-api（backend 直连），非 ai-agent-spa
ssh wuhan-ali "kubectl -n test logs deployment/higress-gateway --since=1m | grep 'system/health' | grep -oE 'route_name...[a-z-]+' | sort | uniq -c"
# 期望: route_name":"ai-agent-api
```

**SPA** — [`ai-agent-ingress.example.yaml`](ai-agent-ingress.example.yaml)（历史整站示例；线上为 `ai-agent-spa`）

- `path: /ai-agent`，`pathType: Prefix` → `frontend:80`
- **必须** `higress.io/timeout: "3600"`（与 API 一致，兜底防 Nginx 反代超时）
- **禁止** rewrite `/ai-agent` → `/`

### 2. giikin-auth-bridge WasmPlugin

[`giikin-auth-bridge-wasmplugin.example.yaml`](giikin-auth-bridge-wasmplugin.example.yaml)（线上 Ingress 名为 **`ai-agent-api`**，namespace `test`）

- 匹配 **HiGress 控制台**创建的路由 `ai-agent-api`（`/ai-agent/api/*`）
- `internal_key` = K8s Secret `GIIKIN_INTERNAL_KEY`
- Redis = **IAM 会话 Redis**（McpBridge 注册 `iam-session-redis.dns`）

**一键部署**（在 wuhan-ali，`/tmp/plugin.wasm` 已存在时）：

```bash
# 1. IAM SSO 回调：清空 Nacos company.sso.redirect-uri（使 callbackOrigin 生效）
/tmp/run-nacos-fix.sh

# 2. 在 VPC 内 push 插件镜像（需 docker + ACR 登录）
/tmp/push-wasm-docker.sh

# 3. 注册 Redis + 应用 WasmPlugin + higress-gateway 拉 ACR 凭据
/tmp/apply-wasmplugin.sh
kubectl -n test patch deploy higress-gateway --type=json \
  --patch-file=/tmp/patch-higress-gateway-acr-pull.json
kubectl -n test rollout restart deploy/higress-gateway
```

验证 binding 回调：

```bash
curl -s 'https://gateway.giimallai.com/api/auth/binding/company_sso?tenantId=000000&domain=admin&callbackOrigin=https://gateway.giimallai.com/ai-agent' \
  | grep '/ai-agent/sso-callback'
```

### 3. ai-agent Backend Secret

```bash
AUTH_MODE=sso
GIIKIN_INTERNAL_KEY=<与 WasmPlugin internal_key 相同>
GIIKIN_SESSION_COOKIE_FALLBACK=false
ROOT_PATH=/ai-agent
```

### 4. 前端镜像

Dockerfile 已默认 `VITE_AUTH_MODE=sso` 与 IAM binding URL；Jenkins 无需额外 build-arg。

---

## 验证命令

```bash
curl -s https://gateway.giimallai.com/ai-agent/api/v1/system/health
curl -s -o /dev/null -w '%{http_code}\n' https://gateway.giimallai.com/ai-agent/api/v1/auth/me
```

---

## 相关文档

- [docs/SSO.md](../../docs/SSO.md) — 架构、流程、故障排查
- [deploy/k8s/README.md](../k8s/README.md) — 镜像发版与 Secret
- giikin 插件源码：`giikin/plugins/giikin-auth-bridge/`
