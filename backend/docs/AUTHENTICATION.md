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
5. **登出**：前端 SSO 模式须 `POST` 同域 IAM `/api/auth/logout`（携带 `guard_token` Cookie），由 `giikin-iam` 清除 Redis 会话并过期 Cookie；仅调 ai-agent `/auth/logout` 或清本地 JWT **无效**。

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

### 2.3 平台角色 vs 团队角色（勿混淆）

| 维度 | 存储 | SSO 首登默认 | 提权方式 |
|------|------|--------------|----------|
| **平台角色** | `users.role` | `user` | Admin API / CLI |
| **团队角色** | `gateway_team_members.role` | personal team → `owner` | 团队成员管理 |

- Giikin SSO Header **不含** `role` / `is_admin`；Giikin IAM 侧管理员**不会**自动映射为本站 `admin`。
- 平台 `admin` 仅在本系统显式授予；SSO 重登**不会**把已提权的 `admin` 改回 `user`（`resolve_or_provision` 命中已有用户后直接返回）。
- 个人团队首登一般为团队 `owner`，与平台 `user` 并存，属正常设计（见 `docs/项目权限规则.md`）。

### 2.4 SSO 用户标识与首个平台 admin

**合成邮箱**：JIT 用户的占位邮箱为 `giikin-{user_id}@giikin.sso`（不可用于本地密码登录）。运维提权或排查时请用此邮箱或用户 UUID：

```bash
# 列出用户（含 giikin 合成邮箱）
uv run python scripts/set_admin.py --list

# 首个平台 admin（仅当尚无 admin 时；SSO 生产无法用本地密码登录）
uv run python scripts/set_admin.py --email giikin-1001@giikin.sso
```

**首个 admin（鸡生蛋）**：生产 `AUTH_MODE=sso` 时，用户经 giikin 登录、无本地 JWT 密码路径。第一个平台管理员须通过：

1. **CLI**（上例 `scripts/set_admin.py`，在目标用户至少 SSO 登录一次以 JIT 建号后执行），或
2. **已有 admin** 在 `/admin/users` 将目标用户平台角色改为 `admin`。

**历史本地账号**：若用户曾在 `local` 模式注册且未绑定 `giikin_user_id`，SSO 首登会 **新建** 一条 JIT 用户。对旧账号提权不会影响 SSO 身份；迁移期需手动绑定：

```sql
UPDATE users SET giikin_user_id = '<giikin_user_id>' WHERE email = '<real_email>';
```

自动化回归见 `tests/integration/api/test_sso_role_persistence.py`。

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
| 前端 | `VITE_SSO_LOGOUT_URL` | 可选；默认同域 `/api/auth/logout`（IAM 登出，清除 guard_token） |
| giikin-iam | `spring.higress.session-cookie-*`（Nacos） | guard_token Cookie 下发开关与属性 |

---

## 5. 关键约束
- `PermissionContext` 仅由 `PermissionContextComposer` + 认证依赖 + 权限中间件装配（架构测试白名单）。
- `/api/v1/gateway/*` 与 `/v1/*` 代理要求已认证身份（无匿名会话）。
- SSO 解析不在网关层落库；JIT 映射统一走 `GiikinIdentityService`。
