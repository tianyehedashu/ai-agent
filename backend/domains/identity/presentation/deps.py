"""
Identity Presentation Dependencies - 身份认证依赖注入

提供身份认证相关的 FastAPI 依赖：
- 当前用户获取
- 认证检查
- 权限校验
"""

from typing import Annotated
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
from domains.identity.application.permission_context_composer import PermissionContextComposer
from domains.identity.presentation.schemas import CurrentUser
from libs.db.database import get_db
from libs.exceptions import PermissionDeniedError
from libs.iam.data_scope_policy import DataAction, DataResource, enforce_data_scope
from libs.iam.permission_context import get_permission_context

__all__ = [
    "ADMIN_ROLE",
    "ANONYMOUS_USER_COOKIE",
    "AdminUser",
    "AuthUser",
    "OptionalAuthUser",
    "OptionalUser",
    "RequiredAuthUser",
    "check_tenant_access",
    "check_tenant_access_or_public",
    "get_current_user",
    "get_current_user_optional",
    "get_user_uuid",
    "require_auth",
    "require_role",
]

security = HTTPBearer(auto_error=False)


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
        vendor_creator_id=principal.vendor_creator_id,
    )

    composer = PermissionContextComposer(db)
    composer.install(await composer.compose_from_principal(principal))

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
        vendor_creator_id=principal.vendor_creator_id,
    )


async def get_current_user_optional_with_anonymous(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
    anonymous_user_id: str | None = Cookie(default=None, alias=ANONYMOUS_USER_COOKIE),
) -> CurrentUser | None:
    """获取当前用户（可选，开发环境支持匿名，生产环境无凭证时返回 None 不抛 401）

    用于需要公开访问的接口（如可用模型列表），无认证时返回 None 而非 401。
    """
    try:
        principal = await get_principal(request, credentials, db, anonymous_user_id)
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise

    current_user = CurrentUser(
        id=principal.id,
        email=principal.email,
        name=principal.name,
        is_anonymous=principal.is_anonymous,
        role=principal.role,
        vendor_creator_id=principal.vendor_creator_id,
    )

    composer = PermissionContextComposer(db)
    composer.install(await composer.compose_from_principal(principal))

    return current_user


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
OptionalAuthUser = Annotated[CurrentUser | None, Depends(get_current_user_optional_with_anonymous)]
AdminUser = Annotated[CurrentUser, Depends(require_role(ADMIN_ROLE))]


def get_user_uuid(current_user: CurrentUser) -> uuid.UUID:
    """从当前用户获取 UUID（用于需要注册用户 ID 的 API）"""
    return uuid.UUID(current_user.id)


# =============================================================================
# 权限检查辅助函数
# =============================================================================


def check_tenant_access(
    resource_tenant_id: uuid.UUID,
    current_user: CurrentUser,
    resource_name: str = "Resource",
) -> None:
    """HTTP 薄适配：委托 ``enforce_data_scope`` 判定 tenant 可见性。"""
    if current_user.role == ADMIN_ROLE:
        return

    ctx = get_permission_context()
    if ctx is None:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )

    allowed = enforce_data_scope(
        ctx,
        DataResource(kind=resource_name, tenant_id=resource_tenant_id),
        DataAction.READ,
    )
    if not allowed:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


def check_tenant_access_or_public(
    resource_tenant_id: uuid.UUID,
    current_user: CurrentUser,
    is_public: bool,
    resource_name: str = "Resource",
) -> None:
    """租户作用域访问，或资源标记为公开。"""
    if is_public:
        return
    check_tenant_access(resource_tenant_id, current_user, resource_name)
