"""Actor-scoped managed team routes aggregate list."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.managed_team_route_reads import (
    list_managed_team_routes_for_actor,
)
from domains.gateway.application.management.route_read_mappers import route_row_to_api_dict
from domains.gateway.presentation.schemas.common import ManagedTeamRouteListResponse, RouteResponse
from domains.identity.presentation.deps import ADMIN_ROLE, RequiredAuthUser, get_user_uuid
from libs.api.pagination import PageParams, build_page, page_query_params
from libs.db.database import get_db

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
PageDep = Annotated[PageParams, Depends(page_query_params)]


@router.get("/managed-team-routes", response_model=ManagedTeamRouteListResponse)
async def list_managed_team_routes(
    current_user: RequiredAuthUser,
    db: DbSession,
    page: PageDep,
) -> ManagedTeamRouteListResponse:
    """列出当前用户 membership 内各团队可见的虚拟路由（跨团队聚合，分页）。"""
    is_platform_admin = current_user.role == ADMIN_ROLE
    result = await list_managed_team_routes_for_actor(
        db,
        user_id=get_user_uuid(current_user),
        is_platform_admin=is_platform_admin,
        page_params=page,
    )
    envelope = build_page(
        items=[
            RouteResponse.model_validate(route_row_to_api_dict(row)) for row in result.page_items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
    return ManagedTeamRouteListResponse(
        **envelope.model_dump(),
        queried_team_count=result.queried_team_count,
        queried_personal_team_count=result.queried_personal_team_count,
        queried_shared_team_count=result.queried_shared_team_count,
        tenant_ids_with_routes=list(result.tenant_ids_with_routes),
    )
