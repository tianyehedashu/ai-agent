"""
HTTP / ASGI 中间件聚合（libs 层）

- **认证**：`AuthMiddleware` 归属身份域，见 ``domains.identity.presentation.middleware``（此处仅 re-export 便于统一发现）。
- **权限 ContextVar**：``PermissionContextASGIMiddleware`` 仅在 ASGI 请求边界预清/清理；真实上下文由认证依赖（如 ``get_current_user``）写入。
- **匿名 Cookie**：``AnonymousCookieASGIMiddleware`` 在 ``http.response.start`` 附加 Set-Cookie；与 ``StreamingResponse`` 兼容（纯 ASGI，非 BaseHTTPMiddleware）。

其余为通用横切（日志、错误处理、限流等）。
"""

from domains.identity.presentation.middleware import AuthMiddleware
from libs.middleware.anonymous_cookie_asgi import AnonymousCookieASGIMiddleware
from libs.middleware.error_handler import ErrorHandlerMiddleware
from libs.middleware.logging import LoggingMiddleware
from libs.middleware.permission import PermissionContextASGIMiddleware
from libs.middleware.rate_limit import RateLimitMiddleware

__all__ = [
    "AnonymousCookieASGIMiddleware",
    "AuthMiddleware",
    "ErrorHandlerMiddleware",
    "LoggingMiddleware",
    "PermissionContextASGIMiddleware",
    "RateLimitMiddleware",
]
