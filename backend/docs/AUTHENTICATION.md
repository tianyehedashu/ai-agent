# 认证与身份（SSO / 本地）

> **生产 SSO 配置与运维**：见项目级文档 **[docs/SSO.md](../../docs/SSO.md)**（HiGress auth-bridge、Secret、验证、排障）。  
> 本文侧重 **backend 实现** 与本地开发。

相关源码：`domains/identity`（`giikin_gateway` / `giikin_identity_service` / `principal_service`）、`bootstrap/config.py`（`auth_mode`）。

---

## 1. 两种认证模式（`AUTH_MODE`）

| 模式 | 取值 | 适用 | 身份来源 |
|------|------|------|----------|
| 本地 | `local`（默认） | 开发 / 本机 | 邮箱密码 + JWT（`Authorization: Bearer`） |
| 单点登录 | `sso` | 生产 | HiGress **giikin-auth-bridge** 注入的 `X-Giikin-*` Header |

切换：后端 `AUTH_MODE` / 前端 `VITE_AUTH_MODE`。两端需一致。

---

## 2. 生产 SSO（backend 视角）

身份解析入口：`resolve_giikin_identity()` → 默认 **仅** `parse_gateway_identity()`（Header）。

| Header | 说明 |
|--------|------|
| `X-Giikin-User-JSON` | Base64 JSON：`user_id`, `name`, `org_code`, `shop_id` |
| `X-Giikin-Internal-Key` | 与 `GIIKIN_INTERNAL_KEY` 一致，防直连伪造 |

`GIIKIN_SESSION_COOKIE_FALLBACK=true` 时才会读 `guard_token` + Redis（**仅本地调试**，生产必须为 `false`）。

### JIT 用户开通

`GiikinIdentityService.resolve_or_provision`：按 `users.giikin_user_id` 映射；未命中则 JIT（`giikin-{id}@giikin.sso`）。

### 平台角色 vs 团队角色

Giikin Header **不含**平台 `admin`；SSO 首登 `users.role=user`，personal team 为 `owner`。详见 [项目权限规则.md](项目权限规则.md)。

### 首个平台 admin

```bash
uv run python scripts/set_admin.py --list
uv run python scripts/set_admin.py --email giikin-1001@giikin.sso
```

---

## 3. 本地开发（`local`）

- `POST /auth/token` 换 JWT；401 时 refresh。
- 前端跳转 `/login`。

---

## 4. 配置项（backend）

| 变量 | 说明 |
|------|------|
| `AUTH_MODE` | `local` / `sso` |
| `GIIKIN_INTERNAL_KEY` | sso 必填，与 auth-bridge 一致 |
| `GIIKIN_SESSION_COOKIE_FALLBACK` | 默认 `false` |

前端与网关配置见 [docs/SSO.md](../../docs/SSO.md)。

---

## 5. 关键约束

- SSO 不在 backend 落库 Giikin 会话；JIT 走 `GiikinIdentityService`。
- 无匿名 Principal / 匿名会话。
- `/api/v1/gateway/*` 要求已认证身份。
