"""跨团队 membership 虚拟路由聚合读侧（actor 维度）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayRoute
from domains.gateway.infrastructure.repositories.gateway_route_repository import (
    GatewayRouteRepository,
)
from domains.tenancy.application.ports import GatewayTeamListingPort
from domains.tenancy.application.team_service import TeamService
from libs.api.pagination import PageParams, slice_page

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

RouteRow = GatewayRoute | SystemGatewayRoute


@dataclass(frozen=True)
class ManagedTeamRouteListPage:
    page_items: tuple[RouteRow, ...]
    total: int
    page: int
    page_size: int
    queried_team_count: int
    queried_personal_team_count: int
    queried_shared_team_count: int
    tenant_ids_with_routes: tuple[uuid.UUID, ...]
    # 路由归属 tenant_id → 团队 kind（personal/shared），供前端区分个人/协作团队路由。
    tenant_kind_by_id: dict[uuid.UUID, str]


async def list_managed_team_routes_for_actor(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    page_params: PageParams,
    team_listing: GatewayTeamListingPort | None = None,
) -> ManagedTeamRouteListPage:
    """列出当前用户 membership 内各团队可见的虚拟路由（含 personal + 协作团队，系统路由按 id 去重）。"""
    listing = team_listing or TeamService(session)
    memberships = await listing.list_gateway_team_memberships(
        user_id,
        is_platform_admin=is_platform_admin,
        search=None,
    )
    tenant_ids = [m.team_id for m in memberships]
    personal_count = sum(1 for m in memberships if m.kind == "personal")
    shared_count = sum(1 for m in memberships if m.kind == "shared")
    tenant_kind_by_id = {m.team_id: m.kind for m in memberships}

    # 团队路由与 system 路由需按 virtual_model 合并去重，暂在应用层 slice_page；
    # 路由数量通常远小于 vkey，避免为合并语义引入过度复杂的 SQL 分页。
    repo = GatewayRouteRepository(session)
    merged = await repo.list_merged_routes_for_tenants(tenant_ids, only_enabled=False)
    page_items, total = slice_page(
        merged,
        page=page_params.page,
        page_size=page_params.page_size,
    )
    tenant_ids_with_routes = tuple(
        sorted(
            {
                row.tenant_id
                for row in merged
                if isinstance(row, GatewayRoute) and row.tenant_id is not None
            }
        )
    )
    return ManagedTeamRouteListPage(
        page_items=tuple(page_items),
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
        queried_team_count=len(tenant_ids),
        queried_personal_team_count=personal_count,
        queried_shared_team_count=shared_count,
        tenant_ids_with_routes=tenant_ids_with_routes,
        tenant_kind_by_id=tenant_kind_by_id,
    )


__all__ = [
    "ManagedTeamRouteListPage",
    "RouteRow",
    "list_managed_team_routes_for_actor",
]
