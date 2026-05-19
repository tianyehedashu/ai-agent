"""虚拟 Key 管理面访问控制（与 revoke / reveal 共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from domains.gateway.domain.errors import (
    SystemVirtualKeyForbiddenError,
    TeamPermissionDeniedError,
    VirtualKeyNotFoundError,
)

if TYPE_CHECKING:
    from uuid import UUID


class VirtualKeyAccessView(Protocol):
    """断言访问权限所需的最小 vkey 视图（结构子类型，ORM 可直接传入）。"""

    team_id: UUID
    is_system: bool
    is_active: bool
    created_by_user_id: UUID | None


def assert_virtual_key_accessible_by_actor(
    record: VirtualKeyAccessView | None,
    *,
    key_id: str,
    team_id: UUID,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
    require_active: bool = True,
) -> VirtualKeyAccessView:
    """校验 actor 是否可访问指定 vkey；失败抛领域异常。"""
    if record is None or record.team_id != team_id:
        raise VirtualKeyNotFoundError(key_id)
    if require_active and not record.is_active:
        raise VirtualKeyNotFoundError(key_id)
    if record.is_system:
        raise SystemVirtualKeyForbiddenError(key_id)
    if (
        not is_platform_admin
        and team_role == "member"
        and record.created_by_user_id != actor_user_id
    ):
        raise TeamPermissionDeniedError(str(team_id))
    return record


def filter_virtual_keys_visible_to_actor(
    keys: list[VirtualKeyAccessView],
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> list[VirtualKeyAccessView]:
    """按 actor 角色过滤 vkey 列表（与 ``assert_virtual_key_accessible_by_actor`` 可见集合一致）。"""
    if is_platform_admin or team_role != "member" or actor_user_id is None:
        return keys
    return [k for k in keys if k.created_by_user_id == actor_user_id]


__all__ = [
    "VirtualKeyAccessView",
    "assert_virtual_key_accessible_by_actor",
    "filter_virtual_keys_visible_to_actor",
]
