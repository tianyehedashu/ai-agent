"""
认证中间件

处理请求认证
"""

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.auth.jwt import verify_token
from utils.logging import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件"""

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
            # 将用户信息添加到请求状态
            request.state.user_id = payload.get("sub")
            request.state.user_role = payload.get("role", "user")
        except Exception as e:
            logger.warning("Token verification failed: %s", e)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token"},
            )

        return await call_next(request)
