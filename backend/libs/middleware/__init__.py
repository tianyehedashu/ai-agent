"""
HTTP 中间件模块

提供请求处理中间件

注意：认证中间件 AuthMiddleware 已移动到 domains.identity.presentation.middleware
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
