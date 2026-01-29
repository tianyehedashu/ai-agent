# 日志系统使用指南

## 概述

项目提供了统一的日志系统，支持后端（Python）和前端（TypeScript）。

## 后端日志

### 基本使用

```python
from utils.logging import get_logger

logger = get_logger(__name__)

logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息", exc_info=True)  # 包含堆栈
```

### 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 调试信息，开发环境使用 |
| INFO | 一般信息，记录正常流程 |
| WARNING | 警告信息，可恢复的问题 |
| ERROR | 错误信息，需要关注 |
| CRITICAL | 严重错误，可能导致系统崩溃 |

### Trace ID 追踪

每个请求会自动生成唯一的 Trace ID，贯穿整个请求生命周期：

```python
# 在代码中使用（Trace ID 会自动注入到日志）
logger.info("处理用户请求")
# 输出: [trace-id:abc123] 2025-01-28 10:00:00 - INFO - 处理用户请求

# 手动设置 Trace 上下文
from utils.logging import set_trace_context
set_trace_context(trace_id="custom-123", user_id="user-456")
```

### 结构化日志

```python
from libs.observability.logging import StructuredLogger

logger = StructuredLogger(__name__)

# 记录事件
logger.log_event("user_login", {"user_id": "123", "ip": "1.2.3.4"})

# 记录 API 调用
logger.log_api_request("GET", "/api/v1/users", status_code=200, duration_ms=45)

# 记录 LLM 调用
logger.log_llm_call(
    model="gpt-4",
    provider="openai",
    prompt_tokens=100,
    completion_tokens=50
)

# 记录 MCP 工具调用
logger.log_mcp_call(
    server_name="filesystem",
    tool_name="read_file",
    success=True,
    duration_ms=120
)
```

### 日志配置

在 `backend/config/app.toml` 中配置：

```toml
[logging]
level = "INFO"           # 日志级别
format = "json"          # 格式: json | text
file = "./logs/app.log"  # 日志文件路径
max_bytes = 10485760      # 单文件最大 10MB
backup_count = 5         # 保留 5 个备份
error_file = "./logs/app.error.log"  # 错误日志
```

### 日志输出位置

- **开发环境**: 控制台 + 文件
- **生产环境**: JSON 格式，便于日志系统收集

日志文件位于：`backend/logs/`

---

## 前端日志

### 基本使用

```typescript
import { createLogger } from '@/lib/logger'

const logger = createLogger('MyComponent')

logger.debug("调试信息")
logger.info("普通信息", { userId: "123" })
logger.warn("警告信息")
logger.error("错误信息", error, { context: "extra data" })
```

### 全局 Logger

```typescript
import { logger } from '@/lib/logger'

// 记录 API 请求
logger.apiRequest("GET", "/api/v1/users")

// 记录 API 响应
logger.apiResponse("GET", "/api/v1/users", 200, 150)

// 记录 API 错误
logger.apiError("POST", "/api/v1/users", error)
```

### 日志级别控制

| 环境 | 显示级别 |
|------|---------|
| development | DEBUG 及以上 |
| production | ERROR 仅 |

### Sentry 集成

错误会自动上报到 Sentry（需配置 `VITE_SENTRY_DSN`）：

```typescript
logger.error("Something went wrong", error, {
  userId: "123",
  action: "submit_form"
})
```

---

## Sentry 配置

### 后端

在 `.env` 文件中配置：

```bash
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
```

### 前端

在 `.env` 文件中配置：

```bash
VITE_SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
```

**依赖包**（已安装）：
- `@sentry/react`
- `@sentry/browser`

---

## 最佳实践

### ✅ DO

- 使用合适的日志级别
- 记录有意义的上下文信息
- 使用结构化日志记录关键事件
- 异常日志使用 `exc_info=True` 或 `logger.exception()`
- 避免记录敏感信息（密码、Token 等）

### ❌ DON'T

- 不要使用 `print()` 记录日志
- 不要在生产环境使用 DEBUG 级别
- 不要在循环中大量记录日志
- 不要记录敏感的用户数据

---

## 快捷参考

```python
# 后端 - 导入
from utils.logging import get_logger, set_trace_context
from libs.observability.logging import StructuredLogger

# 后端 - 创建 logger
logger = get_logger(__name__)
structured_logger = StructuredLogger(__name__)

# 后端 - 使用
logger.info("Message")
structured_logger.log_event("event_type", {"key": "value"})
```

```typescript
// 前端 - 导入
import { createLogger, logger } from '@/lib/logger'

// 前端 - 创建 logger
const log = createLogger('ComponentName')

// 前端 - 使用
log.info("Message", { meta: "data" })
logger.apiRequest("GET", "/api/endpoint")
```
