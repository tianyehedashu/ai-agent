"""
Identity Presentation Dependencies - 身份认证依赖注入

提供身份认证相关的 FastAPI 依赖：
- 当前用户获取
- 认证检查
- 权限校验
"""

from typing import TYPE_CHECKING, Annotated, Protocol

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
from libs.db.database import get_session

if TYPE_CHECKING:
    import uuid

__all__ = [
    "ANONYMOUS_USER_COOKIE",
    "AuthUser",
    "OptionalUser",
    "RequiredAuthUser",
    "SessionLike",
    "check_ownership",
    "check_ownership_or_public",
    "check_session_ownership",
    "get_current_user",
    "get_current_user_optional",
    "require_auth",
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
# 数据库会话辅助
# =============================================================================


async def _get_db() -> AsyncSession:
    """获取数据库会话（内部使用）"""
    async for session in get_session():
        return session
    raise RuntimeError("Failed to get database session")


# =============================================================================
# 认证依赖
# =============================================================================


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(_get_db),
    anonymous_user_id: str | None = Cookie(default=None, alias=ANONYMOUS_USER_COOKIE),
) -> CurrentUser:
    """获取当前用户"""
    principal = await get_principal(request, credentials, db, anonymous_user_id)
    return CurrentUser(
        id=principal.id,
        email=principal.email,
        name=principal.name,
        is_anonymous=principal.is_anonymous,
    )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(_get_db),
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


# 类型别名
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
RequiredAuthUser = Annotated[CurrentUser, Depends(require_auth)]
OptionalUser = Annotated[CurrentUser | None, Depends(get_current_user_optional)]


# =============================================================================
# 权限检查辅助函数
# =============================================================================


def check_ownership(
    resource_user_id: str,
    current_user_id: str,
    resource_name: str = "Resource",
) -> None:
    """检查资源所有权"""
    if str(resource_user_id) != str(current_user_id):
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


def check_ownership_or_public(
    resource_user_id: str,
    current_user_id: str,
    is_public: bool,
    resource_name: str = "Resource",
) -> None:
    """检查资源所有权或是否公开"""
    if str(resource_user_id) != str(current_user_id) and not is_public:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


def check_session_ownership(
    session: "SessionLike",
    current_user: CurrentUser,
) -> None:
    """检查会话所有权（支持注册用户和匿名用户）"""
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
