"""聊天/产品模型选择器中暴露跨团队共享授权路由（委派）。

把共享进团队 T 的路由投影为选择器条目：``id = 暴露别名``，能力/配置取路由**代表 primary
模型**（owner callable 池中第一个可解析者），复用 ``gateway_model_to_selector_item`` 保持
与系统/个人条目同形。实际可调用性仍由热路径委派解析（``_resolve_granted_route``）保证。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.quota.entitlement_model_status import is_connectivity_requestable
from domains.gateway.domain.catalog.registry_model_types import selector_item_matches_ability_filter

from domains.gateway.application.catalog.config_catalog_sync import gateway_model_to_selector_item
from .granted_route_listing import list_granted_route_rows_for_team

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .gateway_model_listing import GatewayRegistryModelRow
    from .granted_route_listing import GrantedRouteRow


def _representative_model(
    route: GrantedRouteRow,
    pool: list[GatewayRegistryModelRow],
) -> GatewayRegistryModelRow | None:
    """路由的代表 primary 模型：按 primary 顺序取 owner 池中首个同名行（裸名或剥离 slug 前缀）。"""
    by_name: dict[str, GatewayRegistryModelRow] = {}
    for m in pool:
        by_name.setdefault(m.name, m)
    for ref in route.primary_models:
        name = ref.split("/", 1)[1] if "/" in ref else ref
        hit = by_name.get(name)
        if hit is not None:
            return hit
    return None


async def list_granted_route_selector_items(
    session: AsyncSession,
    team_id: uuid.UUID,
    *,
    ability_filter: str | None,
) -> list[dict[str, Any]]:
    """团队 T 工作区选择器：共享进 T 的路由条目（已应用能力筛选）。

    个人团队永不作为 grant 消费方（发布侧亦拒绝），故 personal 工作区直接短路，避免无意义查库。
    功能开关由 ``list_granted_route_rows_for_team`` 内部把关。
    """
    from domains.tenancy.application.team_service import TeamService

    team = await TeamService(session).get_team(team_id)
    if team is None or team.kind == "personal":
        return []

    rows, pools = await list_granted_route_rows_for_team(session, team_id, allowed=None)
    items: list[dict[str, Any]] = []
    for route, pool in zip(rows, pools, strict=True):
        rep = _representative_model(route, pool)
        if rep is None or not is_connectivity_requestable(rep.last_test_status):
            continue
        item = gateway_model_to_selector_item(rep)
        alias = route.virtual_model
        item["id"] = alias
        item["model_id"] = alias
        item["display_name"] = alias
        item["enabled"] = True
        item["last_test_status"] = rep.last_test_status
        item["is_shared_route"] = True
        if ability_filter and not selector_item_matches_ability_filter(item, ability_filter):
            continue
        items.append(item)
    return items


__all__ = ["list_granted_route_selector_items"]
