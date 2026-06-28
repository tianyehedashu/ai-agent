"""消费团队代理列表中暴露跨团队共享授权路由（委派）。

把共享进团队 T 的路由投影为"合成路由行"（``virtual_model = 暴露别名``），并附带其
owner 团队的可调用模型池，供 ``build_proxy_models_list`` 解析 capability / 连通性。
路由实际可调用性由热路径委派解析（``_resolve_granted_route``）保证，本投影仅供发现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.management import GatewayManagementReadService

    from .gateway_model_listing import GatewayRegistryModelRow


@dataclass(frozen=True, slots=True)
class GrantedRouteRow:
    """``_build_route_model_list_item`` 所需的最小路由视图（合成，不落库）。"""

    virtual_model: str
    primary_models: list[str]
    tenant_id: uuid.UUID | None = None
    fallbacks_general: list[str] = field(default_factory=list)
    fallbacks_content_policy: list[str] = field(default_factory=list)
    fallbacks_context_window: list[str] = field(default_factory=list)


async def _owner_callable_pool(
    session: AsyncSession,
    *,
    owner_tenant: uuid.UUID,
    owner_user_id: uuid.UUID,
    reads: GatewayManagementReadService,
    cache: dict[uuid.UUID, list[GatewayRegistryModelRow]],
) -> list[GatewayRegistryModelRow]:
    if owner_tenant in cache:
        return cache[owner_tenant]
    from domains.gateway.application.management.personal_route_callable_reads import (
        list_personal_route_owner_callable_pool,
    )
    from domains.tenancy.application.team_service import TeamService

    team = await TeamService(session).get_team(owner_tenant)
    if team is not None and team.kind == "personal":
        pool = await list_personal_route_owner_callable_pool(
            session, owner_user_id=owner_user_id
        )
    else:
        pool = await reads.list_gateway_models(
            owner_tenant,
            registry_scope="callable",
            only_enabled=True,
            user_id=owner_user_id,
        )
    cache[owner_tenant] = pool
    return pool


async def list_granted_route_rows_for_team(
    session: AsyncSession,
    team_id: uuid.UUID,
    *,
    allowed: set[str] | None,
) -> tuple[list[GrantedRouteRow], list[list[GatewayRegistryModelRow]]]:
    """返回 (合成路由行, 每行对应的 owner 团队可调用模型池)。

    owner 缺失 / 路由停用 / 别名不在 allowed 白名单时跳过（与热路径 fail-closed 一致）。
    """
    from bootstrap.config import settings

    if not settings.gateway_route_sharing_enabled:
        return [], []

    from domains.gateway.application.management import GatewayManagementReadService
    from domains.gateway.infrastructure.repositories.gateway_route_grant_repository import (
        GatewayRouteTeamGrantRepository,
    )
    from domains.gateway.infrastructure.repositories.model_repository import (
        GatewayRouteRepository,
    )

    grants = await GatewayRouteTeamGrantRepository(session).list_active_for_tenant(team_id)
    if not grants:
        return [], []

    route_repo = GatewayRouteRepository(session)
    reads = GatewayManagementReadService(session)
    owner_pool_cache: dict[uuid.UUID, list[GatewayRegistryModelRow]] = {}

    route_ids = [g.route_id for g in grants]
    routes_by_id = await route_repo.list_by_ids(route_ids)

    rows: list[GrantedRouteRow] = []
    pools: list[list[GatewayRegistryModelRow]] = []
    for grant in grants:
        if allowed is not None and grant.exposed_alias not in allowed:
            continue
        route = routes_by_id.get(grant.route_id)
        if route is None or not route.enabled or route.created_by_user_id is None:
            continue
        owner_tenant = route.tenant_id
        if owner_tenant is None:
            continue
        pool = await _owner_callable_pool(
            session,
            owner_tenant=owner_tenant,
            owner_user_id=route.created_by_user_id,
            reads=reads,
            cache=owner_pool_cache,
        )
        rows.append(
            GrantedRouteRow(
                virtual_model=grant.exposed_alias,
                primary_models=list(route.primary_models or ()),
                tenant_id=owner_tenant,
            )
        )
        pools.append(pool)
    return rows, pools


__all__ = ["GrantedRouteRow", "list_granted_route_rows_for_team"]
