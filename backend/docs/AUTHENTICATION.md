# 认证与身份（SSO / 本地）

> 本文说明 ai-agent 的登录与身份解析。**ai-agent 不自建生产登录**，生产经 giikin 单点登录（SSO）+ HiGress 网关注入身份；本地开发保留邮箱密码 + JWT 作为回退。
>
> 相关源码：`domains/identity`（principal_service / giikin_gateway / giikin_identity_service / deps）、`bootstrap/config.py`（`auth_mode`）。

---

## 1. 两种认证模式（`AUTH_MODE`）

| 模式 | 取值 | 适用 | 身份来源 |
|------|------|------|----------|
| 本地 | `local`（默认） | 开发 / 本机 | 邮箱密码登录得 JWT（FastAPI Users，HS256），请求带 `Authorization: Bearer` |
| 单点登录 | `sso` | 生产（同域部署在 `gateway.giimallai.com`） | HiGress(`giikin-auth-bridge`) 注入的 `X-Giikin-*` Header |

切换：后端 `AUTH_MODE` / 前端 `VITE_AUTH_MODE`。两端需一致。

> **匿名访客已彻底移除**：不再有匿名 Cookie、匿名 Principal、orphan tenant 新增。历史匿名数据按运维流程清理。注意「平台 `anonymous` 角色」是**另一套**遗留的用户列表过滤概念（见 `platform_role_policy.py`），与本文的「匿名访客机制」无关，未受影响。

---

## 2. 生产 SSO 链路

```
浏览器 ──(guard_token Cookie)──► HiGress ──► ai-agent 后端
                                  │
                                  └─ giikin-auth-bridge WASM 插件
                                     · 读 guard_token Cookie → 查 Redis 会话
                                     · 注入 X-Giikin-User-JSON（Base64 JSON）
                                     · 注入 X-Giikin-Internal-Key
```

1. **登录**：用户访问 ai-agent，未登录则前端整页跳转到 giikin SSO 登录入口（`VITE_SSO_LOGIN_URL`，附 `callbackOrigin`/`redirect`）。
2. **下发 Cookie**：`giikin-iam` 登录成功后由 `UserActionListener` 直接 `Set-Cookie: guard_token=...`（Nacos `spring.higress.session-cookie-*` 配置），实现跨应用会话桥接。
3. **回跳**：登录后回到 ai-agent `/sso-callback`，前端刷新 `GET /auth/me` 并跳回原始页面。
4. **每次请求**：HiGress 校验 Cookie 并注入身份 Header；ai-agent 信任并解析。

### 2.1 身份解析与防伪
`domains/identity/infrastructure/auth/giikin_gateway.py::parse_gateway_identity`：
- 无任何 `X-Giikin-*` Header → 返回 `None`（上层决定是否 401）。
- 配置了 `GIIKIN_INTERNAL_KEY` 时，必须匹配 `X-Giikin-Internal-Key`，否则 `AuthenticationError`（防止绕过网关直连伪造身份）。
- 解码 `X-Giikin-User-JSON`（Base64 JSON）得到 `GiikinGatewayClaims(user_id, name, org_code, shop_id)`。

### 2.2 JIT 用户开通
`domains/identity/application/giikin_identity_service.py::resolve_or_provision`：
- 按 `users.giikin_user_id` 查本地用户；命中直接返回。
- 未命中则即时创建（Just-In-Time）：占位邮箱 `giikin-{user_id}@giikin.sso`、不可登录的随机密码、`role="user"`，并复用默认 personal team 开通逻辑。

`users.giikin_user_id`（`String(64)`，唯一索引，可空）为 SSO 用户与本地用户的映射键（迁移 `20260609_add_user_giikin_user_id`）。

---

## 3. 本地开发链路（`local`）
- `POST /auth/token` 邮箱密码换 access + refresh token。
- 请求带 `Authorization: Bearer`；401 时前端用 refresh token 续期。
- 前端未登录跳转 `/login`。

---

## 4. 配置项

| 端 | 变量 | 说明 |
|----|------|------|
| 后端 | `AUTH_MODE` | `local` / `sso` |
| 后端 | `GIIKIN_INTERNAL_KEY` | sso 模式下与 `giikin-auth-bridge` internal key 对齐 |
| 前端 | `VITE_AUTH_MODE` | `local` / `sso` |
| 前端 | `VITE_SSO_LOGIN_URL` | sso 模式登录入口（完整 URL 或同域路径） |
| giikin-iam | `spring.higress.session-cookie-*`（Nacos） | guard_token Cookie 下发开关与属性 |

---

## 5. 关键约束
- `PermissionContext` 仅由 `PermissionContextComposer` + 认证依赖 + 权限中间件装配（架构测试白名单）。
- `/api/v1/gateway/*` 与 `/v1/*` 代理要求已认证身份（无匿名会话）。
- SSO 解析不在网关层落库；JIT 映射统一走 `GiikinIdentityService`。
