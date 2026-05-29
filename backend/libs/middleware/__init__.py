"""
HTTP / ASGI 中间件聚合（libs 层）

- **权限 ContextVar**：``PermissionContextASGIMiddleware`` 仅在 ASGI 请求边界预清/清理；真实上下文由认证依赖（如 ``get_current_user``）写入。

其余为通用横切（日志、限流等）。**业务异常**由 ``bootstrap/main.py`` 全局 ``exception_handler`` 输出 RFC 7807，不在此重复。
"""

from libs.middleware.logging import LoggingMiddleware
from libs.middleware.permission import PermissionContextASGIMiddleware
from libs.middleware.rate_limit import RateLimitMiddleware

__all__ = [
    "LoggingMiddleware",
    "PermissionContextASGIMiddleware",
    "RateLimitMiddleware",
]
