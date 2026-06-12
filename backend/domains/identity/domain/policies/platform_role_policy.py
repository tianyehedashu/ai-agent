"""平台角色变更策略（纯函数，无 IO）。"""

from __future__ import annotations

import uuid

from domains.identity.domain.rbac import Role
from libs.exceptions import PermissionDeniedError, ValidationError

ASSIGNABLE_PLATFORM_ROLES: frozenset[str] = frozenset(
    {Role.ADMIN.value, Role.USER.value, Role.VIEWER.value}
)

# DEPRECATED：匿名访问能力已移除（见 feat(auth) SSO 重构），不再签发 role='anonymous' 用户，
# 迁移 20260606_anon_tenant 已删除历史 shadow 行。此常量与下方 ANONYMOUS_ROLE 分支仅为防御性
# 兜底，避免遗留库残行被误提权/误邀请。
# 到期条件：确认所有目标库 `SELECT count(*) FROM users WHERE role='anonymous'` 为 0 后，可连同
# user_invite_candidate / sqlalchemy_user_repository / platform_user_admin_policy 的引用一并删除。
ANONYMOUS_ROLE = "anonymous"


def is_assignable_platform_role(role: str) -> bool:
    """目标角色是否为可分配的平台角色。"""
    return role in ASSIGNABLE_PLATFORM_ROLES


def assert_can_change_platform_role(
    *,
    actor_role: str,
    actor_id: uuid.UUID,
    target_id: uuid.UUID,
    target_current_role: str,
    new_role: str,
    admin_count: int | None = None,
) -> None:
    """校验平台管理员是否可为目标用户设置 new_role。

    Args:
        actor_role: 操作者平台角色
        actor_id: 操作者用户 ID
        target_id: 目标用户 ID
        target_current_role: 目标用户当前平台角色
        new_role: 拟设置的平台角色
        admin_count: 当前平台 admin 总数；降级末位 admin 时由 application 传入

    Raises:
        PermissionDeniedError: 无权操作
        ValidationError: 业务规则不允许
    """
    if actor_role != Role.ADMIN.value:
        raise PermissionDeniedError(
            message="Only platform administrators can change platform roles",
            resource="PlatformRole",
        )

    if target_current_role == ANONYMOUS_ROLE:
        raise ValidationError("Cannot assign platform role to anonymous users")

    if not is_assignable_platform_role(new_role):
        raise ValidationError(
            f"Invalid platform role: {new_role}; expected one of "
            f"{', '.join(sorted(ASSIGNABLE_PLATFORM_ROLES))}"
        )

    if actor_id == target_id:
        raise ValidationError("Cannot change your own platform role")

    if (
        target_current_role == Role.ADMIN.value
        and new_role != Role.ADMIN.value
        and admin_count is not None
        and admin_count <= 1
    ):
        raise ValidationError("Cannot demote the last platform administrator")


def assert_bootstrap_grant_admin(
    *,
    target_current_role: str,
    admin_count: int,
) -> None:
    """应急/bootstrap：仅在无平台 admin 时允许将非匿名用户提升为 admin。"""
    if admin_count > 0:
        raise ValidationError(
            "Platform administrator already exists; use Settings or Admin API instead"
        )
    if target_current_role == ANONYMOUS_ROLE:
        raise ValidationError("Cannot assign platform role to anonymous users")
    if target_current_role == Role.ADMIN.value:
        raise ValidationError("User is already a platform administrator")


def assert_bootstrap_revoke_admin(
    *,
    target_current_role: str,
    admin_count: int,
) -> None:
    """应急/bootstrap：仅在至少 2 名 admin 时允许将 admin 降为 user。"""
    if admin_count < 2:
        raise ValidationError(
            "Cannot revoke the last platform administrator; use Settings or Admin API"
        )
    if target_current_role != Role.ADMIN.value:
        raise ValidationError("User is not a platform administrator")


def assert_emergency_grant_admin(*, target_current_role: str) -> None:
    """应急 CLI（--force）：已有 admin 时仍可提升指定用户，禁止匿名与重复提权。"""
    if target_current_role == ANONYMOUS_ROLE:
        raise ValidationError("Cannot assign platform role to anonymous users")
    if target_current_role == Role.ADMIN.value:
        raise ValidationError("User is already a platform administrator")
