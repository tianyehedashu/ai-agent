"""Routes 子 router。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
)
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    RouteCreate,
    RouteResponse,
    RouteUpdate,
)
from libs.exceptions import HttpMappableDomainError

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
    return [RouteResponse.model_validate(r) for r in routes]


@router.post("/routes", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: RouteCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> RouteResponse:
    route = await writes.create_gateway_route(
        team_id=team.team_id,
        virtual_model=body.virtual_model,
        primary_models=body.primary_models,
        fallbacks_general=body.fallbacks_general,
        fallbacks_content_policy=body.fallbacks_content_policy,
        fallbacks_context_window=body.fallbacks_context_window,
        strategy=body.strategy,
        retry_policy=body.retry_policy,
    )
    return RouteResponse.model_validate(route)


@router.patch("/routes/{route_id}", response_model=RouteResponse)
async def update_route(
    route_id: uuid.UUID,
    body: RouteUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> RouteResponse:
    try:
        updated = await writes.update_gateway_route(
            route_id,
            team_id=team.team_id,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return RouteResponse.model_validate(updated)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_gateway_route(route_id, team_id=team.team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


__all__ = ["router"]
