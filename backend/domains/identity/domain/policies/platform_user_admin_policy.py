"""平台用户管理策略（纯函数，无 IO）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.identity.domain.policies.platform_role_policy import (
    ANONYMOUS_ROLE,
    ASSIGNABLE_PLATFORM_ROLES,
    is_assignable_platform_role,
)
from domains.identity.domain.rbac import Role
from libs.exceptions import PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    import uuid


def parse_platform_user_list_role(role: str | None) -> str | None:
    """校验列表筛选的平台角色；None 表示不按角色过滤。"""
    if role is None:
        return None
    if not is_assignable_platform_role(role):
        raise ValidationError(
            f"Invalid platform role filter: {role}; "
            f"expected one of {', '.join(sorted(ASSIGNABLE_PLATFORM_ROLES))}"
        )
    return role


def assert_can_admin_manage_user(*, actor_role: str, target_current_role: str) -> None:
    """校验平台管理员是否可管理目标用户。"""
    if actor_role != Role.ADMIN.value:
        raise PermissionDeniedError(
            message="Only platform administrators can manage users",
            resource="PlatformUser",
        )
    if target_current_role == ANONYMOUS_ROLE:
        raise ValidationError("Cannot manage anonymous users")


def assert_can_set_user_active(
    *,
    actor_id: uuid.UUID,
    target_id: uuid.UUID,
    new_active: bool,
) -> None:
    """校验是否可设置用户启用状态。"""
    if not new_active and actor_id == target_id:
        raise ValidationError("Cannot deactivate your own account")
