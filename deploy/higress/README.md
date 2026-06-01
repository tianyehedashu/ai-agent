# HiGress 接入 AI Agent（SSO + 路由）

公网示例：`http://gateway.giimallai.com/ai-agent/`

**完整 SSO 说明**：[docs/SSO.md](../../docs/SSO.md)

---

## 流量路径

```
gateway.giimallai.com/ai-agent/
    │
    ├─ /ai-agent/assets/*     → frontend Nginx 静态资源
    ├─ /ai-agent/api/*        → frontend Nginx 反代 → backend:8000
    │                              ↑
    │                         HiGress giikin-auth-bridge（WasmPlugin）
    │                         在到达 frontend 前注入 X-Giikin-* Header
    └─ /ai-agent/*            → frontend SPA (index.html)
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

[`ai-agent-ingress.example.yaml`](ai-agent-ingress.example.yaml)

- `path: /ai-agent`，`pathType: Prefix` → `frontend:80`
- **禁止** rewrite `/ai-agent` → `/`
- Chat SSE：`higress.io/timeout: "3600"`
- 请求体：`nginx.ingress.kubernetes.io/proxy-body-size: "50m"`

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
curl -s 'http://gateway.giimallai.com/api/auth/binding/company_sso?tenantId=000000&domain=admin&callbackOrigin=http://gateway.giimallai.com/ai-agent' \
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
curl -s http://gateway.giimallai.com/ai-agent/api/v1/system/health
curl -s -o /dev/null -w '%{http_code}\n' http://gateway.giimallai.com/ai-agent/api/v1/auth/me
```

---

## 相关文档

- [docs/SSO.md](../../docs/SSO.md) — 架构、流程、故障排查
- [deploy/k8s/README.md](../k8s/README.md) — 镜像发版与 Secret
- giikin 插件源码：`giikin/plugins/giikin-auth-bridge/`
