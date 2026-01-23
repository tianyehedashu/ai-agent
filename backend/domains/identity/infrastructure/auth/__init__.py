"""
Auth Infrastructure - 认证基础设施

提供:
- JWT 认证
- 密码加密
- Token 管理
- RBAC 权限控制
"""

from domains.identity.domain.rbac import (
    Permission,
    Role,
    check_resource_ownership,
    has_permission,
)
from domains.identity.infrastructure.auth.jwt import (
    JWTManager,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    get_jwt_manager,
    init_jwt_manager,
    verify_token,
)
from domains.identity.infrastructure.auth.password import hash_password, verify_password
from domains.identity.infrastructure.auth.rbac_adapter import (
    RBACMiddleware,
    require_permission,
)

__all__ = [
    "JWTManager",
    "Permission",
    "RBACMiddleware",
    "Role",
    "TokenPayload",
    "check_resource_ownership",
    "create_access_token",
    "create_refresh_token",
    "get_jwt_manager",
    "has_permission",
    "hash_password",
    "init_jwt_manager",
    "require_permission",
    "verify_password",
    "verify_token",
]
