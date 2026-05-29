"""
Identity Presentation Dependencies - 身份认证依赖注入

提供身份认证相关的 FastAPI 依赖：
- 当前用户获取
- 认证检查
- 权限校验
"""

from typing import Annotated
import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application import (
    get_principal,
    get_principal_optional,
)
from domains.identity.application.permission_context_composer import PermissionContextComposer
from domains.identity.presentation.schemas import CurrentUser
from libs.db.database import get_db
from libs.exceptions import AuthenticationError, PermissionDeniedError
from libs.iam.data_scope_policy import DataAction, DataResource, enforce_data_scope
from libs.iam.permission_context import get_permission_context

__all__ = [
    "ADMIN_ROLE",
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


def _to_current_user(principal: object) -> CurrentUser:
    return CurrentUser(
        id=principal.id,
        email=principal.email,
        name=principal.name,
        role=principal.role,
        vendor_creator_id=principal.vendor_creator_id,
    )


# =============================================================================
# 认证依赖
# =============================================================================


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """获取当前用户并设置权限上下文"""
    principal = await get_principal(request, credentials, db)
    current_user = _to_current_user(principal)

    composer = PermissionContextComposer(db)
    composer.install(await composer.compose_from_principal(principal))

    request.state.current_user = current_user

    return current_user


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    """获取当前用户（可选，无身份返回 None 不抛 401）。"""
    principal = await get_principal_optional(request, credentials, db)
    if not principal:
        return None

    current_user = _to_current_user(principal)
    composer = PermissionContextComposer(db)
    composer.install(await composer.compose_from_principal(principal))
    return current_user


async def require_auth(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求必须认证。"""
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
OptionalAuthUser = Annotated[CurrentUser | None, Depends(get_current_user_optional)]
AdminUser = Annotated[CurrentUser, Depends(require_role(ADMIN_ROLE))]


def get_user_uuid(current_user: CurrentUser) -> uuid.UUID:
    """从当前用户获取 UUID（用于需要注册用户 ID 的 API）"""
    try:
        return uuid.UUID(current_user.id)
    except ValueError as exc:
        raise AuthenticationError("Authentication required") from exc


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
