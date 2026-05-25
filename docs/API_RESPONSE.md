# API 响应与异常处理规范

> **真源**：管理面 REST API（`/api/v1/*`）的成功/错误响应约定。  
> OpenAI / Anthropic 兼容面（`/v1/*`）为**协议例外**，见 [§5](#5-协议例外-openai--anthropic)。  
> 列表分页 envelope 见 [PAGINATION.md](./PAGINATION.md)。

---

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **成功直出** | HTTP 2xx 时 body = Pydantic `response_model`，**不**包 `{ code, message, data }` |
| **错误标准化** | 4xx/5xx 使用 [RFC 7807 Problem Details](https://datatracker.ietf.org/doc/html/rfc7807) + 项目扩展 |
| **异常入口** | 业务层 `raise AIAgentError` 子类；Presentation **禁止** `raise HTTPException`（协议 mapper 白名单除外） |
| **HTTP 语义** | 成败由 **HTTP 状态码** 表达，不由 body 内 `code: 0` 表达 |

---

## 2. 成功响应

Router 声明 `response_model`，JSON 即资源 Schema：

```json
// GET /api/v1/sessions/{id}
{
  "id": "...",
  "title": "...",
  "created_at": "..."
}
```

列表 endpoint 使用分页 envelope（见 [PAGINATION.md](./PAGINATION.md)），仍为 **直出**，不嵌套在 `data` 下。

**禁止** 新 endpoint 返回：

```json
{ "success": true, "data": { ... } }
{ "code": 0, "message": "ok", "data": { ... } }
```

---

## 3. 错误响应（RFC 7807 + 扩展）

实现：`backend/libs/api/problem_details.py`  
全局 handler：`backend/bootstrap/main.py`

### 3.1 Schema

```json
{
  "type": "https://ai-agent.local/errors/not-found",
  "title": "Resource not found",
  "status": 404,
  "detail": "Session not found: abc-123",
  "instance": "/api/v1/sessions/abc-123",
  "code": "NOT_FOUND",
  "errors": [
    { "loc": ["body", "name"], "msg": "field required", "type": "missing" }
  ],
  "extra": { "resource": "Session", "id": "abc-123" }
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `type` | 是 | 错误类型 URI（由 `code` 生成） |
| `title` | 是 | 错误类别概述 |
| `status` | 是 | HTTP 状态码（与响应 status 一致） |
| `detail` | 是 | 当次具体错误消息（**保留**，前端兼容） |
| `instance` | 否 | 请求路径 |
| `code` | 否 | 稳定机器可读码（`libs/exceptions/codes.py`） |
| `errors` | 否 | 字段级错误（422 校验） |
| `extra` | 否 | 业务扩展（原 `details` 字段） |

### 3.2 HTTP 状态 ↔ 异常类

| HTTP | 异常类 | 默认 `code` |
|------|--------|-------------|
| 400 | `ValidationError` | `VALIDATION_ERROR` |
| 401 | `AuthenticationError` / `TokenError` | `AUTHENTICATION_ERROR` / `TOKEN_ERROR` |
| 403 | `PermissionDeniedError` | `PERMISSION_DENIED` |
| 404 | `NotFoundError` | `NOT_FOUND` |
| 409 | `ConflictError` | `CONFLICT` |
| 422 | `RequestValidationError`（FastAPI） | `VALIDATION_ERROR` |
| 429 | `RateLimitError` | `RATE_LIMIT` |
| 502 | `ExternalServiceError` | `EXTERNAL_SERVICE_ERROR` |
| 500 | 未映射 `AIAgentError` / 未知异常 | `INTERNAL_ERROR` |

`HttpMappableDomainError`（Gateway / Tenancy 领域错误）由 `problem_context_from_gateway_domain` 映射，见 `domains/gateway/presentation/http_error_map.py`。

### 3.3 422 字段校验

FastAPI `RequestValidationError` 统一转为 RFC 7807，`errors[]` 保留 `loc` / `msg` / `type`。

---

## 4. 分层职责

```
Domain/Application     raise AIAgentError / HttpMappableDomainError
Presentation Router    response_model 直出；不 catch 再转 HTTPException
bootstrap/main.py      @app.exception_handler → problem_details
Frontend apiClient     2xx → 解析 body 为 T；4xx → ApiError + parseApiErrorBody
```

### 4.1 新增错误码

1. 在 `libs/exceptions/codes.py` 登记常量  
2. 在 `libs/exceptions/__init__.py` 或域 `errors.py` 定义异常类  
3. 若为 `HttpMappableDomainError`，在 `http_error_map.py` 增加映射  
4. 补集成测试断言 `status` + `code` + `detail`

### 4.2 HTTPException 白名单

仅以下文件允许 `raise HTTPException`：

| 文件 | 原因 |
|------|------|
| `domains/gateway/presentation/openai_compat_error_map.py` | OpenAI SDK 错误形 |
| `domains/gateway/presentation/anthropic_compat_router.py` | Anthropic SDK 错误形 |

其他 Presentation / Application 文件禁止新增；架构测试 `tests/architecture/test_no_router_http_exception.py` 守护。

---

## 5. 协议例外：OpenAI / Anthropic

`/v1/chat/completions`、`/v1/messages` 等保持 **上游协议** 错误体，不走 RFC 7807：

**OpenAI：**

```json
{ "error": { "type": "...", "message": "..." } }
```

**Anthropic：**

```json
{ "type": "error", "error": { "type": "...", "message": "..." } }
```

**试调诊断响应头（非 OpenAI 标准，Playground 等调试用）：**

| Header | 含义 |
|--------|------|
| `X-Gateway-Preflight-Ms` | 网关预检（鉴权/限流/预算/kwargs），尚未调用 LiteLLM |
| `X-Gateway-Upstream-Ms` | 网关 → LiteLLM → 厂商 API（非流式完整；流式 MVP 由客户端用总耗时减预检估算） |

---

## 6. 前端约定

| 用途 | 路径 |
|------|------|
| 错误类 | `@/api/errors` → `ApiError`（含 `code`, `title`, `errors`, `extra`） |
| 解析 | `@/lib/fastapi-error-detail` → `parseApiErrorBody` |
| 成功类型 | 各 API adapter 的 `response_model` 对应 TypeScript 类型 |

`ApiClient.request<T>()` 成功时直接返回 `T`（body 即数据）。失败时抛 `ApiError`，优先读 `detail`，结构化字段供 UI 分支。

**禁止** 使用 legacy `ApiResponse<T> { success, data?, error? }`（已移除）。

---

## 7. code-check 核对清单（§16）

### 后端

- [ ] 成功 = Schema 直出；无 `{ success, data }` 包裹
- [ ] 业务错误 `raise AIAgentError`；router 无 `HTTPException`（白名单除外）
- [ ] 新 `code` 登记在 `libs/exceptions/codes.py`
- [ ] `HttpMappableDomainError` 映射在 `http_error_map.py`
- [ ] 集成测试断言 Problem Details 字段

### 前端

- [ ] 经 `parseApiErrorBody` / `ApiError` 处理错误
- [ ] 不用 `any` 重写错误体

---

## 8. 参考实现

| 能力 | 路径 |
|------|------|
| Problem Details | `backend/libs/api/problem_details.py` |
| 错误码 | `backend/libs/exceptions/codes.py` |
| 共享异常 | `backend/libs/exceptions/__init__.py` |
| Gateway 域映射 | `backend/domains/gateway/presentation/http_error_map.py` |
| 全局 handler | `backend/bootstrap/main.py` |
| 前端解析 | `frontend/src/lib/fastapi-error-detail.ts` |
| 架构守护 | `backend/tests/architecture/test_no_router_http_exception.py` |

---

## 9. 迁移说明

- 旧错误体 `{ detail, code, details }` 已扩展为 RFC 7807；`detail` / `code` **保留**
- `details` 重命名为 `extra`（响应体）；旧 key `details` 不再写入新响应
- OpenAI / Anthropic 兼容面**不变**
