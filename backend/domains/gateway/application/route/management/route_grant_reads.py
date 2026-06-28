"""route_grant_reads — 路由跨团队共享授权读服务。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import select

from domains.gateway.domain.route.route_grant_access import assert_actor_owns_route
from domains.gateway.infrastructure.repositories.gateway_route_grant_repository import (
    GatewayRouteTeamGrantRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayRouteRepository
from domains.gateway.presentation.schemas.route_grants import (
    RouteGrantableTeamResponse,
    RouteGrantResponse,
    SharedRouteResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _team_display_by_ids(
    session: AsyncSession, tenant_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, str]]:
    if not tenant_ids:
        return {}
    from domains.tenancy.infrastructure.models.team import Team

    stmt = select(Team.id, Team.name, Team.slug).where(Team.id.in_(tenant_ids))
    result = await session.execute(stmt)
    return {row.id: (row.name, row.slug) for row in result.all()}


async def _route_rows_by_ids(
    session: AsyncSession, route_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, list[str], bool]]:
    if not route_ids:
        return {}
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute

    stmt = select(
        GatewayRoute.id,
        GatewayRoute.virtual_model,
        GatewayRoute.primary_models,
        GatewayRoute.enabled,
    ).where(GatewayRoute.id.in_(route_ids))
    result = await session.execute(stmt)
    return {
        row.id: (row.virtual_model, list(row.primary_models or ()), bool(row.enabled))
        for row in result.all()
    }


async def _user_display_by_ids(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    from domains.identity.application.ports import user_display_label
    from domains.identity.application.user_use_case import UserUseCase

    views = await UserUseCase(session).list_summary_views_by_ids(list(set(user_ids)))
    return {
        uid: label
        for uid, view in views.items()
        if (label := user_display_label(view)) is not None
    }


async def assert_actor_owns_route_by_id(
    session: AsyncSession,
    route_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> uuid.UUID:
    """校验 actor 为路由创建者；返回路由 tenant_id（路由不存在时仍 fail-closed）。"""
    route = await GatewayRouteRepository(session).get(route_id)
    created_by = route.created_by_user_id if route is not None else None
    assert_actor_owns_route(
        route_id=str(route_id),
        route_created_by_user_id=created_by,
        actor_user_id=actor_user_id,
    )
    assert route is not None
    return route.tenant_id


async def list_grantable_teams_for_route_id(
    session: AsyncSession,
    *,
    route_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    fallback_route_tenant_id: uuid.UUID,
) -> list[RouteGrantableTeamResponse]:
    """路由 owner 端点：可共享目标团队（含 ownership 校验）。"""
    route_tenant_id = await assert_actor_owns_route_by_id(session, route_id, actor_user_id)
    existing = await GatewayRouteTeamGrantRepository(session).list_active_for_route(route_id)
    existing_ids = {g.tenant_id for g in existing}
    return await list_grantable_teams_for_route(
        session,
        actor_user_id=actor_user_id,
        route_tenant_id=route_tenant_id or fallback_route_tenant_id,
        existing_grant_tenant_ids=existing_ids,
    )


async def list_route_grants_for_route(
    session: AsyncSession, route_id: uuid.UUID
) -> list[RouteGrantResponse]:
    """路由 owner 视角：列出该路由全部 active 共享授权。"""
    repo = GatewayRouteTeamGrantRepository(session)
    grants = await repo.list_active_for_route(route_id)
    tenant_ids = [g.tenant_id for g in grants]
    team_map = await _team_display_by_ids(session, tenant_ids)
    route_map = await _route_rows_by_ids(session, [route_id])
    virtual_model = route_map.get(route_id, (None, [], True))[0]
    return [
        RouteGrantResponse(
            id=g.id,
            route_id=g.route_id,
            tenant_id=g.tenant_id,
            exposed_alias=g.exposed_alias,
            virtual_model=virtual_model,
            granted_team_name=team_map.get(g.tenant_id, (None, None))[0],
            granted_team_slug=team_map.get(g.tenant_id, (None, None))[1],
            created_at=g.created_at,
        )
        for g in grants
    ]


async def list_shared_routes_for_team(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[SharedRouteResponse]:
    """团队侧视角：列出共享进本团队的全部路由。"""
    repo = GatewayRouteTeamGrantRepository(session)
    grants = await repo.list_active_for_tenant(tenant_id)
    route_ids = [g.route_id for g in grants]
    route_map = await _route_rows_by_ids(session, route_ids)
    owner_ids = [g.granted_by_user_id for g in grants]
    owner_map = await _user_display_by_ids(session, owner_ids)
    rows: list[SharedRouteResponse] = []
    for g in grants:
        virtual_model, primary_models, enabled = route_map.get(
            g.route_id, (None, [], True)
        )
        rows.append(
            SharedRouteResponse(
                grant_id=g.id,
                route_id=g.route_id,
                tenant_id=g.tenant_id,
                exposed_alias=g.exposed_alias,
                virtual_model=virtual_model,
                primary_models=primary_models,
                enabled=enabled,
                owner_user_id=g.granted_by_user_id,
                owner_display=owner_map.get(g.granted_by_user_id),
                created_at=g.created_at,
            )
        )
    return rows


async def list_grantable_teams_for_route(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    route_tenant_id: uuid.UUID,
    existing_grant_tenant_ids: set[uuid.UUID],
) -> list[RouteGrantableTeamResponse]:
    """actor 可共享的目标团队：membership 的 shared 团队 ∖ 路由所属 ∖ 已授权。"""
    from domains.tenancy.infrastructure.models.team import Team, TeamMember

    stmt = (
        select(Team.id, Team.name, Team.slug)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(
            TeamMember.user_id == actor_user_id,
            Team.is_active.is_(True),
            Team.kind == "shared",
            Team.id != route_tenant_id,
        )
    )
    result = await session.execute(stmt)
    rows = [
        RouteGrantableTeamResponse(team_id=row.id, name=row.name, slug=row.slug)
        for row in result.all()
        if row.id not in existing_grant_tenant_ids
    ]
    return rows


__all__ = [
    "assert_actor_owns_route_by_id",
    "list_grantable_teams_for_route",
    "list_grantable_teams_for_route_id",
    "list_route_grants_for_route",
    "list_shared_routes_for_team",
]
