"""vkey 代理端 GET /v1/models 列表合并纯规则。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


def ordered_grant_tenant_ids(
    bound_team_id: UUID,
    granted_team_ids: tuple[UUID, ...],
) -> tuple[UUID, ...]:
    """主属 team 优先，便于 system 裸名先进入 dedupe 集合。"""
    others = tuple(tid for tid in granted_team_ids if tid != bound_team_id)
    return (bound_team_id, *others)


def should_skip_grant_system_model_row(
    *,
    tenant_id: UUID,
    bound_team_id: UUID,
    registry_name: str,
    is_system_registry: bool,
    bound_system_registry_names: frozenset[str],
) -> bool:
    """grant team 的 system 行若主属已以裸名列出，则跳过 prefixed 重复。"""
    if tenant_id == bound_team_id:
        return False
    if not is_system_registry:
        return False
    return registry_name in bound_system_registry_names


def should_skip_grant_system_route_row(
    *,
    tenant_id: UUID,
    bound_team_id: UUID,
    virtual_model: str,
    is_system_registry_route: bool,
    bound_system_registry_names: frozenset[str],
) -> bool:
    """grant team 的 system 路由若主属已裸名列出同名 system 模型，则跳过。"""
    if tenant_id == bound_team_id:
        return False
    if not is_system_registry_route:
        return False
    return virtual_model in bound_system_registry_names


def should_include_multi_grant_entry(
    *,
    tenant_id: UUID,
    bound_team_id: UUID,
    list_id: str,
    seen_list_ids: frozenset[str],
    prefix_dispatchable: bool,
) -> bool:
    """是否纳入 multi-grant 列表（slug 不可派发 / 重复 id 则跳过）。"""
    if not prefix_dispatchable and tenant_id != bound_team_id:
        return False
    return list_id not in seen_list_ids


__all__ = [
    "ordered_grant_tenant_ids",
    "should_include_multi_grant_entry",
    "should_skip_grant_system_model_row",
    "should_skip_grant_system_route_row",
]
