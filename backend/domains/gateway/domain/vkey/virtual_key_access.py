"""虚拟 Key 管理面访问控制（与 revoke / reveal 共用）。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domains.gateway.domain.errors import (
    GatewayTeamHeaderInvalidError,
    GatewayVkeyTeamHeaderMismatchError,
    SystemVirtualKeyForbiddenError,
    VirtualKeyNotFoundError,
)


class VirtualKeyAccessView(Protocol):
    """断言访问权限所需的最小 vkey 视图（结构子类型，ORM 可直接传入）。"""

    tenant_id: UUID
    is_system: bool
    is_active: bool
    created_by_user_id: UUID | None


def actor_owns_non_system_vkey(
    *,
    created_by_user_id: UUID | None,
    actor_user_id: UUID,
    is_system: bool,
) -> bool:
    """非系统 vkey 且创建者为 actor（日志可见性、管理面访问共用）。"""
    return not is_system and created_by_user_id == actor_user_id


def _actor_owns_vkey(
    record: VirtualKeyAccessView,
    actor_user_id: UUID | None,
) -> bool:
    if actor_user_id is None:
        return False
    return actor_owns_non_system_vkey(
        created_by_user_id=record.created_by_user_id,
        actor_user_id=actor_user_id,
        is_system=record.is_system,
    )


def assert_virtual_key_accessible_by_actor(
    record: VirtualKeyAccessView | None,
    *,
    key_id: str,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    require_active: bool = True,
) -> VirtualKeyAccessView:
    """校验 actor 是否可访问指定 vkey；失败抛领域异常。

    虚拟 Key 按**创建者私有**：仅 ``created_by_user_id == actor`` 可列表、揭示、吊销。
    团队所有者/管理员不能查看或使用成员创建的 Key（与团队共享凭据不同）。
    """
    if record is None or record.tenant_id != tenant_id:
        raise VirtualKeyNotFoundError(key_id)
    if require_active and not record.is_active:
        raise VirtualKeyNotFoundError(key_id)
    if record.is_system:
        raise SystemVirtualKeyForbiddenError(key_id)
    if not _actor_owns_vkey(record, actor_user_id):
        raise VirtualKeyNotFoundError(key_id)
    return record


def filter_virtual_keys_visible_to_actor(
    keys: list[VirtualKeyAccessView],
    *,
    actor_user_id: UUID | None,
) -> list[VirtualKeyAccessView]:
    """按创建者过滤 vkey 列表（与 ``assert_virtual_key_accessible_by_actor`` 可见集合一致）。"""
    if actor_user_id is None:
        return []
    return [k for k in keys if _actor_owns_vkey(k, actor_user_id)]


def assert_vkey_team_header_compatible(
    bound_team_id: UUID,
    x_team_id: str | None,
    *,
    granted_team_ids: tuple[UUID, ...] = (),
) -> None:
    """``sk-gw-*`` 已绑定团队；非空且不在主属 ∪ grants 内的 ``X-Team-Id`` 视为客户端误用。"""
    trimmed = (x_team_id or "").strip()
    if not trimmed:
        return
    try:
        header_team_id = UUID(trimmed)
    except ValueError as exc:
        raise GatewayTeamHeaderInvalidError(trimmed) from exc
    # 主属 team 或 granted team 均放行
    allowed = {bound_team_id, *granted_team_ids}
    if header_team_id not in allowed:
        raise GatewayVkeyTeamHeaderMismatchError()


__all__ = [
    "VirtualKeyAccessView",
    "actor_owns_non_system_vkey",
    "assert_virtual_key_accessible_by_actor",
    "assert_vkey_team_header_compatible",
    "filter_virtual_keys_visible_to_actor",
]
