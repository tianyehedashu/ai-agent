"""Identity-related middleware.

身份认证相关的中间件：
- AuthMiddleware: JWT Token 验证中间件
- anonymous_user_cookie_middleware: 匿名用户 Cookie 持久化
"""

from typing import Any

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from bootstrap.config import settings
from domains.identity.application.principal_service import (
    ANONYMOUS_COOKIE_MAX_AGE,
    ANONYMOUS_USER_COOKIE,
    ANONYMOUS_USER_HEADER,
)
from domains.identity.infrastructure.auth.jwt import verify_token
from utils.logging import get_logger

logger = get_logger(__name__)


async def anonymous_user_cookie_middleware(request: Request, call_next) -> Response:
    """
    Persist anonymous user id in cookie and response header.

    认证策略（按优先级）?    1. JWT Token - 已认证用    2. Cookie (anonymous_user_id) - 匿名用户（浏览器自动发送）
    3. Header (X-Anonymous-User-Id) - 匿名用户备用方案（Cookie 丢失时）

    响应行为    - 设置 Cookie 以支持浏览器自动发    - 设置响应X-Anonymous-User-Id 让前端保存到 localStorage
    """
    response = await call_next(request)
    if hasattr(request.state, "anonymous_user_id"):
        anonymous_id = request.state.anonymous_user_id
        # 设置 Cookie
        response.set_cookie(
            key=ANONYMOUS_USER_COOKIE,
            value=anonymous_id,
            max_age=ANONYMOUS_COOKIE_MAX_AGE,
            path="/",  # 确保 Cookie 对所有路径有            httponly=True,
            samesite="lax",
            secure=not settings.is_development,
        )
        # 同时在响应头中返回，让前端可以保存到 localStorage
        # 这样即使 Cookie 丢失，前端也能通过 Header 发送
        response.headers[ANONYMOUS_USER_HEADER] = anonymous_id
    return response


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件

    对需要认证的路由进行 Token 验证
    """

    def __init__(self, app: Any, exclude_paths: list[str] | None = None) -> None:
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """处理请求"""
        # 排除路径
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # 获取 Token
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid authorization header"},
            )

        token = authorization.replace("Bearer ", "")

        # 验证 Token
        try:
            payload = verify_token(token)
            if payload is None:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid token"},
                )
            # 将用户信息添加到请求状态
            request.state.user_id = payload.sub
            request.state.user_role = "user"
        except Exception as e:
            logger.warning("Token verification failed: %s", e)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token"},
            )

        return await call_next(request)
