# AI Agent × Giikin SSO 集成指南

> **生产入口**：`http://gateway.giimallai.com/ai-agent/`  
> **原则**：身份在 **HiGress 网关** 完成（`giikin-auth-bridge`），ai-agent **只读 Header**，**不**直连 IAM Redis。

---

## 1. 架构

```
浏览器
  │  Cookie: guard_token（giikin-iam 登录后下发，Path=/）
  │  GET/POST /ai-agent/api/v1/...
  ▼
HiGress（Ingress 路由 + 超时 + 路径）
  │
  ├─ WasmPlugin: giikin-auth-bridge（仅命中 /ai-agent/api 等需鉴权路由）
  │     · 读 guard_token
  │     · 查 IAM Redis（user:session:{token}，Redisson 前缀 giikin:）
  │     · 注入 X-Giikin-User-JSON / X-Giikin-User-Id / X-Giikin-Internal-Key
  │
  ▼
frontend Pod（Nginx）─ 反代 /ai-agent/api/ ─► backend Pod（FastAPI）
  │
  └─ backend：parse_gateway_identity → JIT 用户 → 业务 API
```

| 组件 | 职责 | 是否读 IAM Redis |
|------|------|------------------|
| **giikin-iam** | 登录、下发 `guard_token`、写 Sa-Token / HiGress Session | 是（权威） |
| **giikin-auth-bridge** | 网关 WASM 插件，Cookie→Header | 是（与 IAM 同实例） |
| **ai-agent backend** | 校验 `X-Giikin-Internal-Key`，解析 Header，JIT 本地用户 | **否** |
| **ai-agent Redis** | 缓存、checkpoint 等应用数据 | **否**（与 IAM 分离） |

静态资源 `/ai-agent/`、`/ai-agent/assets/` 也会经过 auth-bridge（`failStrategy: FAIL_OPEN`，无 Cookie 时透传）；**API** `/ai-agent/api/*` **必须**注入 Header。

> **路由说明**：当前 HiGress 上 `/ai-agent/api/*` 实际命中 Ingress `ai-agent-spa`（frontend nginx 再反代 backend），WasmPlugin 需同时绑定 `ai-agent-api` 与 `ai-agent-spa`；frontend `nginx.conf` 的 `/ai-agent/api/` 须显式 `proxy_set_header X-Giikin-*`，否则网关注入的 Header 在反代时被丢弃。

> **前端 SSO 循环**：`guard_token` 为 **HttpOnly**，不可用 `document.cookie` 判断；auth/me 401 后应使用 SSO 冷却期，避免反复跳 manage.giikin.com。

---

## 2. 用户流程

### 2.1 已在他处登录（plus-ui / 同域 SSO）

1. 浏览器已有 `guard_token`
2. 访问 `/ai-agent/` → `GET /ai-agent/api/v1/auth/me`（`credentials: include`）
3. HiGress auth-bridge 注入 Header → backend 200 → **直接进入应用**，不跳 SSO

### 2.2 未登录

1. `auth/me` → 401
2. 前端 `fetch` `GET /api/auth/binding/company_sso?callbackOrigin=...`（**不可**整页打开 binding URL，会显示 JSON）
3. 取响应 `data` 跳转 `manage.giikin.com` 授权
4. 回调 `callbackOrigin + /sso-callback`（IAM 须优先 `callbackOrigin`，见 giikin `TokenController`）
5. 带 `ticket` 时 ai-agent 会桥接到同域 `/sso-callback`（plus-ui 完成 ticket 换 token + `guard_token`）
6. 用户再访问 `/ai-agent/` 或从 sessionStorage 恢复路径

### 2.3 登出

前端 SSO 模式：`POST /api/auth/logout`（`credentials: include`，**仅**携带 HttpOnly `guard_token`，无 `Authorization` 头）→ IAM 须：

1. 用 Cookie 中的 token 调用 `StpUtil.logoutByTokenValue` 注销 Redis 会话（Sa-Token 默认从 Header 读 token，无 Header 时 `StpUtil.logout()` 会抛 `NotLoginException`）
2. **无论** Sa-Token 是否已登录，都通过 `Set-Cookie` 清除 `guard_token`

完成后前端跳 `/ai-agent/login`（避免落首页触发 `auth/me` 401 后自动 SSO）。若 IAM 未清除 Cookie，刷新后 `auth/me` 仍可能 200，表现为「登出无效」。

---

## 3. 配置清单

### 3.1 HiGress：WasmPlugin（运维）

见 [`deploy/higress/giikin-auth-bridge-wasmplugin.example.yaml`](../deploy/higress/giikin-auth-bridge-wasmplugin.example.yaml)。

要点：

- `internal_key` 与 backend `GIIKIN_INTERNAL_KEY` **完全一致**
- `session_cookie_name: guard_token`
- Redis 指向 **IAM 会话 Redis**（非 ai-agent 应用 Redis）
- `matchRules` 绑定 Ingress `ai-agent-api` 与 `ai-agent-spa`（当前 API 流量经 spa→nginx 反代）

### 3.2 HiGress：Ingress（运维）

见 [`deploy/higress/ai-agent-ingress.example.yaml`](../deploy/higress/ai-agent-ingress.example.yaml)。

- `path: /ai-agent`，`pathType: Prefix` → `frontend:80`
- **勿** rewrite 掉 `/ai-agent` 前缀
- SSE：`higress.io/timeout: "3600"`

### 3.3 K8s Secret：`ai-agent-backend-env`

| 变量 | 生产值 | 说明 |
|------|--------|------|
| `AUTH_MODE` | `sso` | |
| `GIIKIN_INTERNAL_KEY` | 与 WasmPlugin `internal_key` 相同 | 防直连伪造 Header |
| `GIIKIN_SESSION_COOKIE_FALLBACK` | `false` | **勿**改为 true（除非本地调试） |
| `ROOT_PATH` | `/ai-agent` | 无尾随空格 |
| `REDIS_URL` | ai-agent **自有** Redis | **不要**为 SSO 去对齐 IAM Redis |

### 3.4 前端构建（Dockerfile 已带默认）

| 变量 | 默认 |
|------|------|
| `VITE_APP_ROOT` | `/ai-agent` |
| `VITE_AUTH_MODE` | `sso` |
| `VITE_SSO_LOGIN_URL` | `http://gateway.giimallai.com/api/auth/binding/company_sso?tenantId=000000&domain=admin` |

### 3.5 giikin-iam（Nacos）

| 配置 | 说明 |
|------|------|
| `spring.higress.session-cookie-enabled: true` | 登录下发 `guard_token` |
| `spring.higress.session-cookie-path: /` | 同域子路径可用 |
| `company.sso.redirect-uri` | 留空或低优先级；**binding 带 `callbackOrigin` 时应优先** `callbackOrigin/sso-callback` |

---

## 4. 验证

```bash
# 1. 健康检查（无需登录）
curl -s http://gateway.giimallai.com/ai-agent/api/v1/system/health

# 2. 未登录
curl -s -o /dev/null -w '%{http_code}\n' http://gateway.giimallai.com/ai-agent/api/v1/auth/me
# 期望 401

# 3. 已登录（浏览器 Cookie 或 -b guard_token=...）
curl -s -b 'guard_token=YOUR_TOKEN' http://gateway.giimallai.com/ai-agent/api/v1/auth/me
# 期望 200 + 用户信息

# 4. 确认 Header 注入（在 backend Pod 内看 access log 或临时 debug）
# 应出现 X-Giikin-User-JSON、X-Giikin-Internal-Key
```

---

## 5. 故障排查

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 已登录仍跳 SSO | auth-bridge 未命中 `/ai-agent/api` | 检查 WasmPlugin `matchRules` |
| 有 Cookie 但 auth/me 401，页面提示「无法识别 Giikin 登录态」 | 有 Cookie 无 Header | 启用 auth-bridge；勿开 cookie 回退 |
| 第一次访问显示 binding JSON | 前端整页打开 binding URL | 已修复：`initiateSsoLogin` fetch 后跳转 |
| SSO 后落到 `/index` | 回调走 plus-ui `/sso-callback` | IAM 优先 `callbackOrigin`；完成后手动进 `/ai-agent/` |
| 401 Invalid gateway internal key | internal_key 不一致 | 对齐 WasmPlugin 与 Secret |
| 直连 backend ClusterIP 可伪造身份 | 绕过网关 | SSO 模式必须配 `GIIKIN_INTERNAL_KEY`，fail-closed |

---

## 6. 代码索引

| 模块 | 路径 |
|------|------|
| Header 解析 | `backend/domains/identity/infrastructure/auth/giikin_gateway.py` |
| JIT 用户 | `backend/domains/identity/application/giikin_identity_service.py` |
| Cookie 回退（仅 `GIIKIN_SESSION_COOKIE_FALLBACK=true`） | `backend/domains/identity/infrastructure/auth/giikin_session_cookie.py` |
| 前端 SSO | `frontend/src/config/auth.ts`、`frontend/src/components/auth-provider.tsx` |
| auth-bridge 插件（giikin 仓库） | `giikin/plugins/giikin-auth-bridge/` |

后端实现细节（JIT、平台角色、本地模式）见 [backend/docs/AUTHENTICATION.md](../backend/docs/AUTHENTICATION.md)。

---

## 7. 反模式（勿用）

- ai-agent backend **共用 IAM Redis** 解析 `guard_token`（热修方案，已废弃）
- 生产 `GIIKIN_SESSION_COOKIE_FALLBACK=true`
- 仅配 Secret 不配 HiGress auth-bridge
- `redirect-uri` 写死 plus-ui 且忽略 ai-agent 的 `callbackOrigin`
