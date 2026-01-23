"""
RBAC Domain - 基于角色的访问控制领域模型

包含:
- 角色和权限定义（领域概念）
- 权限映射规则（业务规则）
- 权限检查业务逻辑
"""

from enum import Enum


class Role(str, Enum):
    """用户角色 - 领域值对象"""

    ADMIN = "admin"  # 管理员
    USER = "user"  # 普通用户
    VIEWER = "viewer"  # 只读用户


class Permission(str, Enum):
    """权限 - 领域值对象"""

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


# 角色-权限映射（业务规则）
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
    检查角色是否拥有权限（业务逻辑）

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


def check_resource_ownership(
    user_id: str,
    resource_user_id: str,
    user_role: str = "user",
) -> bool:
    """
    检查资源所有权（业务逻辑）

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
