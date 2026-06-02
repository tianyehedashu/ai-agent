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
  │     · 查 IAM Redis（user:session:{token}，与 IAM 写入 key 一致）
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
| **ai-agent backend** | 校验 `X-Giikin-Internal-Key`，解析 Header，JIT 本地用户；hybrid 下也接受本地 JWT | **否**（SSO 通道不读 IAM Redis） |
| **ai-agent Redis** | 缓存、checkpoint 等应用数据 | **否**（与 IAM 分离） |

静态资源 `/ai-agent/`、`/ai-agent/assets/` 也会经过 auth-bridge（`failStrategy: FAIL_OPEN`，无 Cookie 时透传）；**API** `/ai-agent/api/*` **必须**注入 Header。

**单次 API 请求路径**（与 §2.1 一致）：

```mermaid
flowchart TB
    subgraph Client["浏览器"]
        REQ["GET /ai-agent/api/v1/..."]
        CK["Cookie: guard_token"]
    end

    subgraph Higress["HiGress Gateway"]
        ING["Ingress ai-agent-spa"]
        WASM["giikin-auth-bridge Wasm<br/>matchRules: ai-agent-spa + ai-agent-api"]
        REDIS[("IAM Redis<br/>user:session:{token}")]
    end

    subgraph Pod["ai-agent Pod"]
        NGX["Nginx :80<br/>/ai-agent/api/ → backend:8000"]
        BE["FastAPI<br/>parse_gateway_identity → JIT"]
    end

    REQ --> ING
    CK --> WASM
    ING --> WASM
    WASM -->|"1. 读 guard_token"| WASM
    WASM -->|"2. GET session"| REDIS
    WASM -->|"3. 注入 Header"| NGX
    NGX -->|"proxy_set_header<br/>X-Giikin-*"| BE

    WASM -.->|"无 Cookie / session 未命中<br/>FAIL_OPEN 不注入"| NGX
```

**auth-bridge 鉴权分支**（`failStrategy: FAIL_OPEN`）：

```mermaid
flowchart TD
    A["收到请求"] --> B{"Cookie 含<br/>guard_token?"}
    B -->|否| Z["不注入 Header<br/>透传 downstream"]
    B -->|是| C["Redis GET<br/>user:session:{token}"]
    C --> D{key 存在?}
    D -->|是| E["注入 X-Giikin-User-JSON<br/>X-Giikin-User-Id<br/>X-Giikin-Internal-Key"]
    D -->|否| F["session_not_found<br/>不注入 Header"]
    E --> G["继续转发"]
    F --> G
    Z --> G
    G --> H["backend: 有 Header → 200<br/>无 Header → 401"]
```

**IAM 写入路径**（登录时，与 Wasm 读取 key 一致，见 §2.5）：

```mermaid
flowchart LR
    LOGIN["POST /api/auth/login"] --> L["UserActionListener.doLogin"]
    L --> S1["Sa-Token 会话"]
    L --> S2["SET user:session:{jwt}<br/>TTL = client.timeout"]
    L --> S3["Set-Cookie guard_token<br/>Max-Age 同源"]
```

> **路由说明**：当前 HiGress 上 `/ai-agent/api/*` 实际命中 Ingress `ai-agent-spa`（frontend nginx 再反代 backend），WasmPlugin 需同时绑定 `ai-agent-api` 与 `ai-agent-spa`；frontend `nginx.conf` 的 `/ai-agent/api/` 须显式 `proxy_set_header X-Giikin-*`，否则网关注入的 Header 在反代时被丢弃。

> **前端 SSO 循环**：`guard_token` 为 **HttpOnly**，不可用 `document.cookie` 判断；auth/me 401 后应使用 SSO 冷却期，避免反复跳 manage.giikin.com。

### 1.1 术语与角色（流程图图例）

下文流程图中的 **`[归属]`** 前缀表示代码/服务所在仓库或层级，避免与 giikin 同名概念混淆。

| 文档称呼 | 归属 | 代码 / 路径 | 说明 |
|----------|------|-------------|------|
| **`AuthProvider`** | `[ai-agent]` 前端 | `frontend/src/components/auth-provider.tsx`，挂载于 `App.tsx` | 全局认证守卫：除公开页外阻塞渲染、调 `auth/me`、401 跳 SSO、冷却期重试 |
| **`SsoCallbackPage`** | `[ai-agent]` 前端 | `frontend/src/pages/auth/sso-callback.tsx` | SSO 回调页；Router 路径 `/sso-callback`，公网 URL **`/ai-agent/sso-callback`** |
| **`auth.ts` 工具** | `[ai-agent]` 前端 | `frontend/src/config/auth.ts` | `initiateSsoLogin`、`clearStaleGiikinSession`、冷却期 `markSsoAttempt`、`isHybridMode`、`showLocalLogin` 等 |
| **`plus-ui /sso-callback`** | `[giikin]` 前端 | `giikin-iam-plus-ui` | 网关根路径 **`/sso-callback`**（无 `/ai-agent` 前缀）；plus-ui 自身 SSO 入口；ai-agent 不再依赖此页换票 |
| **`giikin-iam`** | `[giikin]` 后端 | IAM 服务 | binding、login、logout；`UserActionListener` 写 Redis + Cookie |
| **`giikin-auth-bridge`** | `[HiGress]` Wasm | `giikin/plugins/giikin-auth-bridge/` | 读 Cookie → 查 IAM Redis → 注入 `X-Giikin-*` |
| **`ai-agent backend`** | `[ai-agent]` 后端 | FastAPI | SSO: 只读 Header + Internal-Key；hybrid: Bearer JWT 优先 |

**两条易混 URL**（同域 `gateway.giimallai.com`）：

| 公网路径 | 归属 | 用途 |
|----------|------|------|
| `/ai-agent/sso-callback` | ai-agent SPA | IAM 带 `ticket` 的首跳；`SsoCallbackPage` 调后端换票后重载校验 `auth/me` |
| `/sso-callback` | plus-ui | plus-ui 自身 SSO 入口；ai-agent 不再调用此路径 |

---

## 2. 用户流程

> 下列时序与 §1.1 术语表中的组件一致。  
> **公开页**（`[ai-agent] AuthProvider` 不触发自动 SSO）：Router `/login`、`/register`、`/sso-callback` → 公网 `/ai-agent/login` 等；其中 **`/sso-callback` 由 `SsoCallbackPage` 自行处理**。

### 2.0 场景一览

```mermaid
flowchart TB
    Start(["用户访问 /ai-agent/*"]) --> Public{Router 路径∈<br/>/login /register /sso-callback?}
    Public -->|/login /register| LoginPage["公开页直接渲染<br/>不调 auth/me"]
    Public -->|/sso-callback| CallbackFlow["§2.2 阶段 B<br/>[ai-agent] SsoCallbackPage"]
    Public -->|否| AuthMe["[ai-agent] AuthProvider<br/>GET /ai-agent/api/v1/auth/me"]
    AuthMe --> HasUser{200 有用户?}
    HasUser -->|是| App["进入应用"]
    HasUser -->|否 401| HasJwt{hybrid 模式<br/>且本地有 JWT?}
    HasJwt -->|是| LocalExpired["JWT 过期<br/>跳 /login（可选 SSO 或邮箱重新登录）"]
    HasJwt -->|否| Cooldown{SSO 冷却期<br/>120s 内?}
    Cooldown -->|否| InitSSO["§2.2 阶段 A<br/>auth.ts initiateSsoLogin"]
    Cooldown -->|是| Retry["[ai-agent] AuthProvider<br/>重试 auth/me 8×500ms"]
    Retry --> Still401{仍 401?}
    Still401 -->|否| App
    Still401 -->|是| Stale["§2.4 auth.ts<br/>clearStaleGiikinSession"]
    InitSSO --> SSOFlow["§2.2 完整 SSO 链路"]
    SSOFlow --> App
    CallbackFlow --> App
    Stale --> SSOFlow
    LoginPage -.->|"用户点击 Giikin SSO 登录"| InitSSO
    LoginPage -.->|"hybrid: 用户点击<br/>「邮箱密码登录」"| LocalLogin["POST /auth/token<br/>本地 JWT 登录"]
    LocalLogin --> App

    Logout(["用户登出"]) --> LogoutFlow["§2.3 user.ts logout<br/>→ giikin-iam + 清 JWT"]
    LogoutFlow --> LoginPage
```

> **公开页与受保护页的差异**：`AuthProvider` 对 `/login`、`/register`、`/sso-callback` 不发起 `auth/me`，因此不会自动触发 SSO。`/login` 的 SSO 入口须由用户在登录页点击 "Giikin SSO 登录" 按钮触发（见 [`frontend/src/pages/auth/login.tsx`](../frontend/src/pages/auth/login.tsx)），便于在 SSO 异常时仍能进入本地登录或手动重试。

> **hybrid 双通道**：`AUTH_MODE=hybrid` 时，后端同时接受 `Authorization: Bearer` JWT 与网关 `X-Giikin-*` Header。**优先级**：Bearer JWT > 网关 Header。邮箱登录用户走 JWT 路径；SSO 登录用户走 Cookie→Wasm→Header 路径。若同一浏览器两种凭证并存，以 JWT 身份为准。

### 2.1 已在他处登录（plus-ui / 同域 SSO）

**前提**：浏览器 Cookie 中已有有效 `guard_token`，且 IAM Redis 存在对应 `user:session:{token}`（例如在 plus-ui 已完成 SSO）。

1. 访问 `/ai-agent/` → **`[ai-agent] AuthProvider`** 发起 `GET /ai-agent/api/v1/auth/me`（`credentials: include`）
2. HiGress `giikin-auth-bridge` 读 Cookie → 查 Redis → 注入 `X-Giikin-*`
3. frontend Nginx 反代时**透传**上述 Header → backend 校验 Internal-Key、JIT 本地用户 → **200**
4. **不**调用 binding、**不**跳转 manage.giikin.com

```mermaid
sequenceDiagram
    autonumber
    participant B as 浏览器
    participant AP as [ai-agent]<br/>AuthProvider
    participant HG as [HiGress]<br/>auth-bridge Wasm
    participant R as IAM Redis
    participant NG as [ai-agent]<br/>frontend Nginx
    participant BE as [ai-agent]<br/>backend

    Note over B: 已在 plus-ui / 同域 SSO<br/>Cookie: guard_token（HttpOnly）

    B->>AP: 加载 SPA /ai-agent/
    AP->>HG: GET /ai-agent/api/v1/auth/me<br/>Cookie: guard_token
    HG->>HG: 读 Cookie guard_token
    HG->>R: GET user:session:{token}
    R-->>HG: {"user_id","org_code","name",...}
    HG->>NG: 请求 + X-Giikin-User-JSON<br/>+ X-Giikin-Internal-Key
    NG->>BE: proxy_set_header 透传 X-Giikin-*
    BE->>BE: 校验 Internal-Key<br/>解析 Header → JIT User
    BE-->>AP: 200 CurrentUser
    AP-->>B: 渲染业务页（不跳 SSO）
```

### 2.2 未登录（冷启动 SSO）

分两阶段：**A** 从 401 到公司 SSO 并带回 `ticket`；**B** 在 ai-agent 内换票、写 Cookie、确认 `auth/me`。

#### 2.2.1 阶段 A：401 → 公司 SSO 授权

1. `auth/me` → **401**（无 Cookie，或 Wasm 未注入 Header）
2. **`[ai-agent] AuthProvider`** 判定非冷却期 → **`auth.ts`** `initiateSsoLogin(path)`
3. `sessionStorage` 写入 `ai_agent_sso_return_path`；`markSsoAttempt()` 开启 **120s 冷却期**
4. **`fetch`**（非整页导航）`GET /api/auth/binding/company_sso?callbackOrigin=http://gateway.../ai-agent&domain=...`
5. 响应 JSON `{ code:200, data: authorizeUrl }` → `location.href = authorizeUrl`（manage.giikin.com）
6. 用户在公司 IdP 授权后，IAM 302 到 **`{callbackOrigin}/sso-callback?ticket=...`**，即 `/ai-agent/sso-callback?ticket=...`

```mermaid
sequenceDiagram
    autonumber
    participant B as 浏览器
    participant AP as [ai-agent]<br/>AuthProvider
    participant HG as [HiGress]<br/>Gateway
    participant IAM as [giikin]<br/>giikin-iam
    participant EXT as 公司 SSO<br/>manage.giikin.com
    participant BE as [ai-agent]<br/>backend

    B->>AP: 访问 /ai-agent/chat（受保护页）
    AP->>HG: GET /ai-agent/api/v1/auth/me
    Note over HG: 无 guard_token 或 session 未命中<br/>failStrategy: FAIL_OPEN，不注入 Header
    HG->>BE: 无 X-Giikin-*
    BE-->>AP: 401
    AP->>AP: sessionStorage 存 returnPath<br/>markSsoAttempt() 冷却 120s
    AP->>IAM: fetch GET /api/auth/binding/company_sso<br/>?callbackOrigin=.../ai-agent
    IAM-->>AP: { code:200, data: authorizeUrl }
    AP->>B: window.location = authorizeUrl
    B->>EXT: 用户登录 / 授权
    EXT->>IAM: OAuth 回调
    IAM->>B: 302 Location<br/>/ai-agent/sso-callback?ticket=T
```

#### 2.2.2 阶段 B：ticket 换票 → guard_token → 进入应用

1. **`/ai-agent/sso-callback?ticket=T`**：**`[ai-agent] AuthProvider`** 对该 Router 路径 **defer** `auth/me`（Query `enabled: false`），由 **`SsoCallbackPage`** 接管
2. 有 `ticket` → `markSsoAttempt()` → **`SsoCallbackPage`** 调用 **`POST /ai-agent/api/v1/auth/sso-exchange`**，将 ticket 发给 ai-agent 后端
3. ai-agent 后端通过 HiGress 网关调用 **`POST /api/auth/login`**（`grantType=company_sso`，**JSON 明文**，不加密）
4. **`[giikin]` IAM** `UserActionListener.doLogin`：写 Sa-Token、**`user:session:{token}`**（TTL 与 client.timeout 对齐）、`Set-Cookie: guard_token`
5. IAM 响应经 HiGress 返回 ai-agent 后端，后端从响应头提取 `guard_token` 值 → **以无 Domain 方式重新 `Set-Cookie: guard_token`**，使 Cookie 落在 `gateway.giimallai.com` 域下
6. ai-agent 后端返回 `{"ok":true}` → `SsoCallbackPage` **整页重载** `/ai-agent/sso-callback`（无 ticket）
7. **`SsoCallbackPage`** `fetchCurrentUserWithRetry`：**最多 10 次 × 500ms** 调 `auth/me`；成功则 `clearSsoAttempt()`，`navigate` 到 `sessionStorage` 中的 returnPath

> **为何绕过 plus-ui `/sso-callback`？**
> 原架构依赖 plus-ui 在同域 `gateway.giimallai.com/sso-callback` 完成 `POST /api/auth/login` 换票，IAM 返回的 `Set-Cookie` 经 HiGress 转发到浏览器时应落在 `gateway.giimallai.com`。
> 但实际部署中 IAM 配置了 `sessionCookieDomain=.giikin.com`（Nacos `spring.higress.session-cookie-domain`），导致浏览器收到 `Domain=.giikin.com` 的 `Set-Cookie` 却被拒绝（因响应来自 `gateway.giimallai.com` 而非 `.giikin.com` 子域）。
> 现由 ai-agent 后端接管换票，从 IAM 响应中提取 `guard_token` 并以无 Domain 方式重设，确保 Cookie 落在正确的 `gateway.giimallai.com` 域下。

```mermaid
sequenceDiagram
    autonumber
    participant B as 浏览器
    participant CB as [ai-agent]<br/>SsoCallbackPage
    participant BE as [ai-agent]<br/>backend
    participant HG as [HiGress]<br/>auth-bridge Wasm
    participant IAM as [giikin]<br/>giikin-iam
    participant R as IAM Redis

    B->>CB: GET /ai-agent/sso-callback?ticket=T
    Note over CB: [ai-agent] AuthProvider<br/>对本页 defer auth/me
    CB->>CB: markSsoAttempt()
    CB->>BE: POST /ai-agent/api/v1/auth/sso-exchange<br/>{"ticket":"T"}

    BE->>HG: POST /api/auth/login (company_sso, 明文 JSON)
    HG->>IAM: 转发 login
    IAM->>R: SET user:session:{jwt}
    IAM->>IAM: Sa-Token 会话
    IAM-->>HG: Set-Cookie guard_token (Domain=.giikin.com)<br/>200 access_token
    HG-->>BE: 转发（headers 保留）

    BE->>BE: 提取 guard_token 值，<br/>以无 Domain 方式重新 Set-Cookie
    BE-->>B: Set-Cookie guard_token (无 Domain)<br/>{"ok":true}
    B->>B: Cookie 落在 gateway.giimallai.com

    CB->>B: location.replace → /ai-agent/sso-callback（无 ticket）
    B->>CB: GET /ai-agent/sso-callback（无 ticket）
    loop 最多 10 次，间隔 500ms
        CB->>HG: GET /ai-agent/api/v1/auth/me<br/>Cookie: guard_token
        HG->>R: GET user:session:{jwt}
        R-->>HG: session JSON
        HG->>BE: X-Giikin-* + Internal-Key
        BE-->>CB: 200 / 401
    end
    CB->>CB: clearSsoAttempt()
    CB->>B: navigate → returnPath（如 /chat）
```

### 2.3 登出

前端 SSO 模式（**`[ai-agent]`** [`user.ts`](../frontend/src/stores/user.ts) `logout`）：

1. `POST /api/auth/logout`（`credentials: include`，**仅** Cookie 带 `guard_token`，无 `Authorization`）
2. IAM `SysLoginService`：从 Cookie 读 token → `StpUtil.logoutByTokenValue`；**无论** Sa-Token 是否已失效，均 `Set-Cookie` 清除 `guard_token`
3. 删 Redis：`Sa-Token` 相关 key + `user:session:{token}`
4. 前端 `clearSsoAttempt()`、`clearAuth()` → **`window.location.href = /ai-agent/login`**（避免落首页再次触发自动 SSO）

```mermaid
sequenceDiagram
    autonumber
    participant B as 浏览器
    participant FE as [ai-agent]<br/>user.ts logout
    participant IAM as [giikin]<br/>giikin-iam
    participant R as IAM Redis

    B->>FE: 点击登出
    FE->>IAM: POST /api/auth/logout<br/>Cookie: guard_token
    IAM->>IAM: readGuardTokenFromRequest()<br/>logoutByTokenValue(token)
    IAM->>R: DEL Sa-Token 键<br/>DEL user:session:{token}
    IAM-->>B: Set-Cookie guard_token=; Max-Age=0
    FE->>FE: clearSsoAttempt() / clearAuth()
    FE->>B: location → /ai-agent/login
    Note over B,FE: 勿 redirect 到 /<br/>否则 auth/me 401 会再触发 §2.2
```

### 2.4 陈旧 Cookie 自愈（登录已过期）

**触发条件**：浏览器仍带 `guard_token`，但 Redis **`user:session:{token}` 不存在**（过期、顶号、TTL 曾不同步等）。Wasm 日志常见 `session not found`；`failStrategy: FAIL_OPEN` 下**不注入 Header** → backend **401**。

| 入口 | 负责组件 | 行为 |
|------|----------|------|
| **`/ai-agent/sso-callback`**（换票后） | **`[ai-agent] SsoCallbackPage`** | 10×500ms 重试 `auth/me` 失败 → `clearStaleGiikinSession()` → **自动 `initiateSsoLogin()` 重新拉起 SSO**；再失败才落到「重新登录」按钮 |
| **其他受保护页 + 冷却期内** | **`[ai-agent] AuthProvider`** | 8×500ms 重试 → 仍 401 → `clearStaleGiikinSession()` → `initiateSsoLogin()` |
| **冷却期外 401** | **`[ai-agent] AuthProvider`** | 直接 `initiateSsoLogin()`（§2.2 阶段 A） |

> **回调页与 AuthProvider 自愈对称**：换票后 10 次重试失败时，`SsoCallbackPage` 会先 `clearStaleGiikinSession`，再把当前 `target` 回写到 `sessionStorage`（避免丢失原 returnPath），随后自动 `initiateSsoLogin`，行为与 `AuthProvider` 在受保护页冷却期内的处理一致。

**`clearStaleGiikinSession()`**（`auth.ts`）= `POST /api/auth/logout`，强制清除 HttpOnly Cookie（JS 无法直接删）。

```mermaid
flowchart TD
    subgraph Wasm["[HiGress] giikin-auth-bridge"]
        W1["读 Cookie guard_token"] --> W2{"Redis<br/>user:session:{token}"}
        W2 -->|命中| W3["注入 X-Giikin-*"]
        W2 -->|未命中| W4["FAIL_OPEN<br/>不注入 Header"]
    end

    W3 --> OK["[ai-agent] backend<br/>auth/me → 200"]
    W4 --> U401["[ai-agent] backend<br/>auth/me → 401"]

    U401 --> Where{Router 路径?}
    Where -->|/sso-callback| CB["[ai-agent] SsoCallbackPage<br/>重试 10×500ms"]
    Where -->|其他 + 冷却期内| AP["[ai-agent] AuthProvider<br/>重试 8×500ms"]
    Where -->|其他 + 冷却期外| SSO["auth.ts initiateSsoLogin<br/>§2.2 阶段 A"]

    CB --> CBFail{仍 401?}
    CBFail -->|否| OK
    CBFail -->|是| Clear1["clearStaleGiikinSession"]
    Clear1 --> AutoSSO1["自动 initiateSsoLogin<br/>与 AuthProvider 对称"]
    AutoSSO1 --> OK
    AutoSSO1 -->|失败| Err["展示「重新登录」按钮"]

    AP --> APFail{仍 401?}
    APFail -->|否| OK
    APFail -->|是| Clear2["clearStaleGiikinSession"]
    Clear2 --> SSO
    SSO --> OK
```

### 2.5 IAM 会话与 Cookie 生命周期（权威写入）

登录 / 续期 / 登出时，**`[giikin]` IAM** 须保持 **Sa-Token、`user:session:{token}`、`guard_token` Cookie** 三者一致（`UserActionListener`、`HigressUserSessionRedisServiceImpl`）。

```mermaid
stateDiagram-v2
    [*] --> 未登录
    未登录 --> 已登录: doLogin<br/>SET user:session TTL=client.timeout<br/>Set-Cookie guard_token Max-Age 同源
    已登录 --> 已登录: doRenewTimeout<br/>EXPIRE user:session 延长
    已登录 --> 未登录: doLogout<br/>DEL session + 清 Cookie
    已登录 --> 未登录: doKickout / doReplaced<br/>DEL session + 若 Cookie 匹配则清 Cookie
    note right of 已登录
        Wasm 只读 user:session:{token}
        与 Cookie 中 jwt 必须一致
    end note
```

---

## 3. 配置清单

### 3.1 HiGress：WasmPlugin（运维）

见 [`deploy/higress/giikin-auth-bridge-wasmplugin.example.yaml`](../deploy/higress/giikin-auth-bridge-wasmplugin.example.yaml)。

要点：

- `internal_key` 与 backend `GIIKIN_INTERNAL_KEY` **完全一致**
- `session_cookie_name: guard_token`
- Redis 指向 **IAM 会话 Redis**（非 ai-agent 应用 Redis）
- `matchRules` 绑定 Ingress `ai-agent-api` 与 `ai-agent-spa`（当前 API 流量经 spa→nginx 反代）

**运维增强建议**：当前 `failStrategy: FAIL_OPEN`（无 Cookie / session 未命中时透传），便于 SPA 静态资源无感通过。但 **API 路由**建议单独配置为 `FAIL_CLOSED`：

```yaml
# 推荐：SPA 静态资源 FAIL_OPEN，API 路由 FAIL_CLOSED
matchRules:
  - ingress: ai-agent-spa
    failStrategy: FAIL_OPEN      # 静态资源无 Cookie 仍可加载
  - ingress: ai-agent-api
    failStrategy: FAIL_CLOSED    # session 缺失时网关直接 401，便于区分「网关层鉴权失败」与「backend 业务 401」
```

> `FAIL_CLOSED` 下，Wasm 在 session 未命中时直接返回 401（不转发到 backend），响应体含 `session_not_found` 等标识，便于前端与运维快速定位是网关层还是业务层问题。

### 3.2 HiGress：Ingress（运维）

见 [`deploy/higress/ai-agent-ingress.example.yaml`](../deploy/higress/ai-agent-ingress.example.yaml)。

- `path: /ai-agent`，`pathType: Prefix` → `frontend:80`
- **勿** rewrite 掉 `/ai-agent` 前缀
- SSE：`higress.io/timeout: "3600"`

### 3.3 K8s Secret：`ai-agent-backend-env`

| 变量 | 生产值 | 说明 |
|------|--------|------|
| `AUTH_MODE` | `sso` 或 `hybrid` | `sso` = 仅 SSO；`hybrid` = SSO + 邮箱密码双通道 |
| `GIIKIN_INTERNAL_KEY` | 与 WasmPlugin `internal_key` 相同 | 防直连伪造 Header（`sso`/`hybrid` 必填） |
| `ALLOW_REGISTER` | `false` | hybrid 模式下建议禁止公开注册，由管理员创建邮箱账号 |
| `GIIKIN_SESSION_COOKIE_FALLBACK` | `false` | **勿**改为 true（除非本地调试） |
| `ROOT_PATH` | `/ai-agent` | 无尾随空格 |
| `REDIS_URL` | ai-agent **自有** Redis | **不要**为 SSO 去对齐 IAM Redis |

### 3.4 前端构建（Dockerfile 已带默认）

| 变量 | 默认 |
|------|------|
| `VITE_APP_ROOT` | `/ai-agent` |
| `VITE_AUTH_MODE` | `sso` / `local` / `hybrid`（生产建议 `hybrid`） |
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
| 有 Cookie 但 auth/me 401 /「登录已过期」 | 浏览器 `guard_token` 与 Redis `user:session` 不同步（过期、顶号、TTL 漂移） | 前端会 logout 后重走 SSO；IAM 须对齐 Cookie 与 session TTL（见 giikin `UserActionListener`） |
| 频繁出现「登录已过期」自愈循环 | giikin-iam 未升级到包含 session/Cookie 生命周期修复的版本 | 升级 giikin-iam 镜像（含 `HigressUserSessionRedisServiceImpl` TTL 对齐、`doRenewTimeout`、kickout/replaced 清 Cookie 修复，commit `55871aa` 或更新） |
| 有 Cookie 无 Header（Wasm 未注入） | auth-bridge 未命中或未配置 | 检查 WasmPlugin `matchRules`；勿开 cookie 回退 |
| 第一次访问显示 binding JSON | 前端整页打开 binding URL | 已修复：`initiateSsoLogin` fetch 后跳转 |
| SSO 后落到 `/index` | 回调走 plus-ui `/sso-callback` | IAM 优先 `callbackOrigin`；完成后手动进 `/ai-agent/` |
| 401 Invalid gateway internal key | internal_key 不一致 | 对齐 WasmPlugin 与 Secret |
| 直连 backend ClusterIP 可伪造身份 | 绕过网关 | SSO 模式必须配 `GIIKIN_INTERNAL_KEY`，fail-closed |
| 难以区分「网关未注入 Header」与「backend 内部 401」 | API 路由 Wasm 仍为 `FAIL_OPEN` | 建议为 `ai-agent-api` 单独配 `failStrategy: FAIL_CLOSED`（见 §3.1） |
| hybrid 下邮箱登录后刷新仍以 SSO 身份进入 | JWT 过期后 fallback 到网关 Header，Cookie 仍有效 | 正常行为（Bearer 优先，JWT 过期才 fallback）；若需切换身份，先登出再登录 |
| hybrid 下 `/auth/register` 返回 404 | `ALLOW_REGISTER=false` | 通过管理员接口或脚本创建邮箱用户 |
| SSO 后 auth/me 始终 401、无 guard_token（网关域） | IAM 配置了 `session-cookie-domain=.giikin.com`，导致 `guard_token` Domain 与 `gateway.giimallai.com` 不匹配 | ai-agent 后端已接管换票（`/api/v1/auth/sso-exchange`），从 IAM 响应提取 `guard_token` 并以无 Domain 方式重设 Cookie |

---

## 6. 代码索引

| 文档称呼 | 归属 | 路径 |
|----------|------|------|
| **`AuthProvider`** | `[ai-agent]` 前端 | [`frontend/src/components/auth-provider.tsx`](../frontend/src/components/auth-provider.tsx)（挂载于 [`App.tsx`](../frontend/src/App.tsx)） |
| **`SsoCallbackPage`** | `[ai-agent]` 前端 | [`frontend/src/pages/auth/sso-callback.tsx`](../frontend/src/pages/auth/sso-callback.tsx) |
| SSO 工具函数 | `[ai-agent]` 前端 | [`frontend/src/config/auth.ts`](../frontend/src/config/auth.ts)（`isSsoMode`、`isHybridMode`、`showLocalLogin`） |
| 登录页 | `[ai-agent]` 前端 | [`frontend/src/pages/auth/login.tsx`](../frontend/src/pages/auth/login.tsx)（hybrid: SSO 按钮 + 折叠邮箱表单） |
| 登出 | `[ai-agent]` 前端 | [`frontend/src/stores/user.ts`](../frontend/src/stores/user.ts) `logout` |
| 身份解析 | `[ai-agent]` 后端 | [`backend/domains/identity/application/principal_service.py`](../backend/domains/identity/application/principal_service.py)（hybrid: Bearer 优先 → fallback 网关 Header） |
| **SSO 换票** | `[ai-agent]` 后端 | [`backend/domains/identity/presentation/router.py`](../backend/domains/identity/presentation/router.py) `/api/v1/auth/sso-exchange`（后端调用 IAM login → 提取 guard_token → 无 Domain 重设 Cookie） |
| Header 解析 | `[ai-agent]` 后端 | [`backend/domains/identity/infrastructure/auth/giikin_gateway.py`](../backend/domains/identity/infrastructure/auth/giikin_gateway.py) |
| JIT 用户 | `[ai-agent]` 后端 | [`backend/domains/identity/application/giikin_identity_service.py`](../backend/domains/identity/application/giikin_identity_service.py) |
| 认证模式配置 | `[ai-agent]` 后端 | [`backend/bootstrap/config.py`](../backend/bootstrap/config.py)（`auth_mode`、`allow_register`） |
| Cookie 回退（已废弃） | `[ai-agent]` 后端 | `giikin_session_cookie.py`（仅 `GIIKIN_SESSION_COOKIE_FALLBACK=true`） |
| IAM 会话写入 | `[giikin]` 后端 | `giikin-iam/.../UserActionListener.java`、`HigressUserSessionRedisServiceImpl.java` |
| **`giikin-auth-bridge`** | `[HiGress]` Wasm | `giikin/plugins/giikin-auth-bridge/` |
| plus-ui 换票页 | `[giikin]` 前端 | `giikin-iam-plus-ui/.../sso-callback.vue` |

后端实现细节（JIT、平台角色、本地模式）见 [backend/docs/AUTHENTICATION.md](../backend/docs/AUTHENTICATION.md)。

---

## 7. 反模式（勿用）

- ai-agent backend **共用 IAM Redis** 解析 `guard_token`（热修方案，已废弃）
- 生产 `GIIKIN_SESSION_COOKIE_FALLBACK=true`
- 仅配 Secret 不配 HiGress auth-bridge
- `redirect-uri` 写死 plus-ui 且忽略 ai-agent 的 `callbackOrigin`
- hybrid 模式下 `ALLOW_REGISTER=true` 且无管理员审核（公开注册暴露内部系统）
- hybrid 模式下 `AUTH_MODE=local`（丢失 SSO 能力，应使用 `hybrid`）
