"""
RBAC - 基于角色的访问控制

实现:
- 角色定义
- 权限检查
- 资源访问控制
"""

from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any

from fastapi import HTTPException, status

from utils.logging import get_logger

logger = get_logger(__name__)


class Role(str, Enum):
    """用户角色"""

    ADMIN = "admin"  # 管理员
    USER = "user"  # 普通用户
    VIEWER = "viewer"  # 只读用户


class Permission(str, Enum):
    """权限"""

    # Agent 权限
    AGENT_CREATE = "agent:create"
    AGENT_READ = "agent:read"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_EXECUTE = "agent:execute"

    # Session 权限
    SESSION_CREATE = "session:create"
    SESSION_READ = "session:read"
    SESSION_DELETE = "session:delete"

    # Workflow 权限
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_UPDATE = "workflow:update"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_PUBLISH = "workflow:publish"

    # 系统权限
    SYSTEM_ADMIN = "system:admin"
    USER_MANAGE = "user:manage"


# 角色-权限映射
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),  # 管理员拥有所有权限
    Role.USER: {
        Permission.AGENT_CREATE,
        Permission.AGENT_READ,
        Permission.AGENT_UPDATE,
        Permission.AGENT_DELETE,
        Permission.AGENT_EXECUTE,
        Permission.SESSION_CREATE,
        Permission.SESSION_READ,
        Permission.SESSION_DELETE,
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_UPDATE,
        Permission.WORKFLOW_DELETE,
    },
    Role.VIEWER: {
        Permission.AGENT_READ,
        Permission.SESSION_READ,
        Permission.WORKFLOW_READ,
    },
}


def has_permission(role: Role | str, permission: Permission) -> bool:
    """
    检查角色是否拥有权限

    Args:
        role: 用户角色
        permission: 权限

    Returns:
        是否拥有权限
    """
    if isinstance(role, str):
        try:
            role = Role(role)
        except ValueError:
            return False

    permissions = ROLE_PERMISSIONS.get(role, set())
    return permission in permissions


def require_permission(permission: Permission):
    """
    权限要求装饰器

    用于 FastAPI 路由

    Args:
        permission: 所需权限
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, current_user: dict | None = None, **kwargs):
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            user_role = current_user.get("role", "user")

            if not has_permission(user_role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value}",
                )

            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator


def check_resource_ownership(
    user_id: str,
    resource_user_id: str,
    user_role: str = "user",
) -> bool:
    """
    检查资源所有权

    Args:
        user_id: 当前用户 ID
        resource_user_id: 资源所有者 ID
        user_role: 用户角色

    Returns:
        是否有权限访问
    """
    # 管理员可以访问所有资源
    if user_role == Role.ADMIN.value:
        return True

    # 其他用户只能访问自己的资源
    return user_id == resource_user_id


class RBACMiddleware:
    """
    RBAC 中间件

    可选：用于更细粒度的权限控制
    """

    def __init__(self, required_permissions: list[Permission] | None = None):
        self.required_permissions = required_permissions or []

    async def __call__(
        self,
        current_user: dict[str, Any],
    ) -> bool:
        """检查权限"""
        user_role = current_user.get("role", "user")

        for permission in self.required_permissions:
            if not has_permission(user_role, permission):
                return False

        return True
