"""虚拟 Key 管理面访问控制（与 revoke / reveal 共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from domains.gateway.domain.errors import (
    SystemVirtualKeyForbiddenError,
    VirtualKeyNotFoundError,
)

if TYPE_CHECKING:
    from uuid import UUID


class VirtualKeyAccessView(Protocol):
    """断言访问权限所需的最小 vkey 视图（结构子类型，ORM 可直接传入）。"""

    tenant_id: UUID
    is_system: bool
    is_active: bool
    created_by_user_id: UUID | None


def _actor_owns_vkey(
    record: VirtualKeyAccessView,
    actor_user_id: UUID | None,
) -> bool:
    return actor_user_id is not None and record.created_by_user_id == actor_user_id


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
    return [k for k in keys if _actor_owns_vkey(k, actor_user_id) and not k.is_system]


__all__ = [
    "VirtualKeyAccessView",
    "assert_virtual_key_accessible_by_actor",
    "filter_virtual_keys_visible_to_actor",
]
