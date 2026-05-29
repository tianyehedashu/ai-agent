"""Identity Presentation Layer - 身份认证表示层

提供身份认证相关的 API 组件：
- deps: 认证依赖注入（AuthUser, RequiredAuthUser, AdminUser, OptionalUser, check_*）
- schemas: 请求/响应模型（CurrentUser, UserCreate, UserLogin 等）
- router: API 路由
"""

from domains.identity.presentation.deps import (
    ADMIN_ROLE,
    AdminUser,
    AuthUser,
    OptionalUser,
    RequiredAuthUser,
    check_tenant_access,
    check_tenant_access_or_public,
    get_current_user,
    get_current_user_optional,
    require_auth,
    require_role,
)
from domains.identity.presentation.schemas import (
    CurrentUser,
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRead,
    UserResponse,
    UserUpdate,
)

__all__ = [
    # Role constants
    "ADMIN_ROLE",
    # Dependencies
    "AdminUser",
    "AuthUser",
    # Schemas
    "CurrentUser",
    "OptionalUser",
    "PasswordChange",
    "RequiredAuthUser",
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserRead",
    "UserResponse",
    "UserUpdate",
    "check_tenant_access",
    "check_tenant_access_or_public",
    "get_current_user",
    "get_current_user_optional",
    "require_auth",
    "require_role",
]
