"""Routes 子 router。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.route_grant_reads import (
    list_shared_routes_for_team,
)
from domains.gateway.application.management.route_read_mappers import route_row_to_api_dict
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
)
from domains.gateway.presentation.schemas.common import (
    RouteCreate,
    RouteResponse,
    RouteUpdate,
)
from domains.gateway.presentation.schemas.route_grants import SharedRouteResponse
from libs.db.database import get_db

from ._common import (
    MgmtReads,
    MgmtWrites,
)

router = APIRouter()


@router.get("/routes", response_model=list[RouteResponse])
async def list_routes(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[RouteResponse]:
    routes = await reads.list_gateway_routes(team.team_id, only_enabled=False)
    return [RouteResponse.model_validate(route_row_to_api_dict(r)) for r in routes]


@router.post("/routes", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: RouteCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> RouteResponse:
    route = await writes.create_gateway_route(
        tenant_id=team.team_id,
        virtual_model=body.virtual_model,
        primary_models=body.primary_models,
        fallbacks_general=body.fallbacks_general,
        fallbacks_content_policy=body.fallbacks_content_policy,
        fallbacks_context_window=body.fallbacks_context_window,
        strategy=body.strategy.value,
        retry_policy=body.retry_policy,
        actor_user_id=team.user_id,
    )
    return RouteResponse.model_validate(route_row_to_api_dict(route))


@router.patch("/routes/{route_id}", response_model=RouteResponse)
async def update_route(
    route_id: uuid.UUID,
    body: RouteUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> RouteResponse:
    updated = await writes.update_gateway_route(
        route_id,
        tenant_id=team.team_id,
        fields=body.model_dump(exclude_unset=True, exclude_none=True),
        actor_user_id=team.user_id,
    )
    return RouteResponse.model_validate(route_row_to_api_dict(updated))


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    await writes.delete_gateway_route(route_id, tenant_id=team.team_id)


@router.get("/shared-routes", response_model=list[SharedRouteResponse])
async def list_shared_routes(
    team: CurrentTeam,
    db: AsyncSession = Depends(get_db),
) -> list[SharedRouteResponse]:
    """列出共享进本团队的路由（成员可见，只读）。"""
    return await list_shared_routes_for_team(db, team.team_id)


@router.delete("/shared-routes/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eject_shared_route(
    grant_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    """团队 owner/admin 把共享路由踢出本团队。"""
    await writes.revoke_route_grant_by_id_for_team(
        grant_id=grant_id,
        team_id=team.team_id,
        actor_user_id=team.user_id,
        actor_team_role=team.team_role,
        reason="team_admin_revoked",
    )


__all__ = ["router"]
