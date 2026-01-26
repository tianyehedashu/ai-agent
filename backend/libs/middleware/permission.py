"""
Permission Context Middleware - 权限上下文中间件

在请求开始时从认证信息创建 PermissionContext，供 Repository 层使用。
"""

from contextlib import suppress
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from domains.identity.domain.types import Principal
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


class PermissionContextMiddleware(BaseHTTPMiddleware):
    """权限上下文中间件

    在请求开始时从认证信息创建 PermissionContext，
    供 Repository 层使用。

    依赖于认证依赖（get_current_user）已经将用户信息设置到 request.state。
    由于 FastAPI 依赖注入的执行顺序，此中间件需要在路由处理之前设置上下文。

    注意：此中间件主要用于需要在中间件层面访问权限上下文的场景。
    对于大多数情况，可以在依赖注入中直接设置上下文。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求"""
        try:
            # 尝试从 request.state 获取用户信息
            # 这些信息由认证依赖设置
            ctx = None

            if hasattr(request.state, "current_user"):
                user = request.state.current_user
                # 解析用户身份
                user_id = None
                anonymous_user_id = None

                if hasattr(user, "is_anonymous") and user.is_anonymous:
                    # 匿名用户
                    anonymous_user_id = Principal.extract_anonymous_id(user.id)
                else:
                    # 注册用户
                    with suppress(ValueError, AttributeError):
                        user_id = uuid.UUID(user.id)

                role = getattr(user, "role", "user")

                ctx = PermissionContext(
                    user_id=user_id,
                    anonymous_user_id=anonymous_user_id,
                    role=role,
                )

            set_permission_context(ctx)
            response = await call_next(request)
            return response
        finally:
            # 清理上下文
            clear_permission_context()


__all__ = ["PermissionContextMiddleware"]
