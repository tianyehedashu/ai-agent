"""
Identity Presentation Dependencies - 身份认证依赖注入

提供身份认证相关的 FastAPI 依赖：
- 当前用户获取
- 认证检查
- 权限校验
"""

from contextlib import suppress
from typing import Annotated, Protocol
import uuid

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.identity.application import (
    ANONYMOUS_USER_COOKIE,
    get_principal,
    get_principal_optional,
)
from domains.identity.domain.types import Principal
from domains.identity.presentation.schemas import CurrentUser
from exceptions import PermissionDeniedError
from libs.api.deps import get_db
from libs.db.permission_context import PermissionContext, set_permission_context

__all__ = [
    "ADMIN_ROLE",
    "ANONYMOUS_USER_COOKIE",
    "AdminUser",
    "AuthUser",
    "OptionalUser",
    "RequiredAuthUser",
    "SessionLike",
    "check_ownership",
    "check_ownership_or_public",
    "check_session_ownership",
    "get_current_user",
    "get_current_user_optional",
    "get_user_uuid",
    "require_auth",
    "require_role",
]

security = HTTPBearer(auto_error=False)


# =============================================================================
# 类型协议
# =============================================================================


class SessionLike(Protocol):
    """会话协议（用于 check_session_ownership 的 duck typing）"""

    user_id: "uuid.UUID | None"
    anonymous_user_id: str | None


# =============================================================================
# 认证依赖
# =============================================================================


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
    anonymous_user_id: str | None = Cookie(default=None, alias=ANONYMOUS_USER_COOKIE),
) -> CurrentUser:
    """获取当前用户并设置权限上下文"""
    principal = await get_principal(request, credentials, db, anonymous_user_id)
    current_user = CurrentUser(
        id=principal.id,
        email=principal.email,
        name=principal.name,
        is_anonymous=principal.is_anonymous,
        role=principal.role,
    )

    # 设置权限上下文供 Repository 层使用
    user_id = None
    anonymous_id = None

    if principal.is_anonymous:
        anonymous_id = principal.get_anonymous_user_id()
    else:
        with suppress(ValueError, AttributeError):
            user_id = uuid.UUID(principal.id)

    ctx = PermissionContext(
        user_id=user_id,
        anonymous_user_id=anonymous_id,
        role=principal.role,
    )
    set_permission_context(ctx)

    # 同时设置到 request.state 供中间件使用（如果中间件需要）
    request.state.current_user = current_user

    return current_user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    """获取当前用户（可选）"""
    principal = await get_principal_optional(credentials, db)
    if not principal:
        return None
    return CurrentUser(
        id=principal.id,
        email=principal.email,
        name=principal.name,
        is_anonymous=principal.is_anonymous,
        role=principal.role,
    )


async def require_auth(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求必须认证（非匿名）"""
    if settings.is_development:
        return current_user
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


# =============================================================================
# 角色依赖
# =============================================================================

# 角色常量
ADMIN_ROLE = "admin"
USER_ROLE = "user"
VIEWER_ROLE = "viewer"


def require_role(*roles: str):
    """要求特定角色的依赖工厂

    Args:
        *roles: 允许的角色列表

    Returns:
        FastAPI 依赖函数

    Example:
        @router.get("/admin-only")
        async def admin_only(user: Annotated[CurrentUser, Depends(require_role("admin"))]):
            ...
    """

    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in roles:
            raise PermissionDeniedError(
                message=f"Required role: {', '.join(roles)}",
                resource="Role",
            )
        return current_user

    return dependency


# 类型别名
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
RequiredAuthUser = Annotated[CurrentUser, Depends(require_auth)]
OptionalUser = Annotated[CurrentUser | None, Depends(get_current_user_optional)]
AdminUser = Annotated[CurrentUser, Depends(require_role(ADMIN_ROLE))]


def get_user_uuid(current_user: CurrentUser) -> uuid.UUID:
    """从当前用户获取 UUID（用于需要注册用户 ID 的 API）"""
    return uuid.UUID(current_user.id)


# =============================================================================
# 权限检查辅助函数
# =============================================================================


def check_ownership(
    resource_user_id: str,
    current_user: CurrentUser,
    resource_name: str = "Resource",
) -> None:
    """检查资源所有权（管理员可访问所有资源）

    Args:
        resource_user_id: 资源所有者 ID
        current_user: 当前用户
        resource_name: 资源名称（用于错误消息）

    Raises:
        PermissionDeniedError: 如果无权访问
    """
    # 管理员可以访问所有资源
    if current_user.role == ADMIN_ROLE:
        return

    if str(resource_user_id) != current_user.id:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


def check_ownership_or_public(
    resource_user_id: str,
    current_user: CurrentUser,
    is_public: bool,
    resource_name: str = "Resource",
) -> None:
    """检查资源所有权或是否公开（管理员可访问所有资源）

    Args:
        resource_user_id: 资源所有者 ID
        current_user: 当前用户
        is_public: 资源是否公开
        resource_name: 资源名称（用于错误消息）

    Raises:
        PermissionDeniedError: 如果无权访问
    """
    # 管理员可以访问所有资源
    if current_user.role == ADMIN_ROLE:
        return

    if str(resource_user_id) != current_user.id and not is_public:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


def check_session_ownership(
    session: "SessionLike",
    current_user: CurrentUser,
) -> None:
    """检查会话所有权（支持注册用户和匿名用户，管理员可访问所有会话）

    Args:
        session: 会话对象
        current_user: 当前用户

    Raises:
        PermissionDeniedError: 如果无权访问
    """
    # 管理员可以访问所有会话
    if current_user.role == ADMIN_ROLE:
        return

    if current_user.is_anonymous:
        user_anonymous_id = Principal.extract_anonymous_id(current_user.id)
        if session.anonymous_user_id != user_anonymous_id:
            raise PermissionDeniedError(
                message="You don't have permission to access this session",
                resource="Session",
            )
    else:
        if str(session.user_id) != current_user.id:
            raise PermissionDeniedError(
                message="You don't have permission to access this session",
                resource="Session",
            )
