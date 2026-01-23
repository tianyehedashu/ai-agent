"""
Identity Domain - 身份识别领域

包含领域模型、值对象、领域服务和业务规则
"""

from domains.identity.domain.rbac import (
    Permission,
    Role,
    check_resource_ownership,
    has_permission,
)

__all__ = [
    "Permission",
    "Role",
    "check_resource_ownership",
    "has_permission",
]
