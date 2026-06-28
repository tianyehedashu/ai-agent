"""User-scoped personal virtual routes 子 router。"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.route.management.personal_route_callable_reads import (
    list_personal_route_callable_models_for_actor,
    route_callable_model_to_response_dict,
)
from domains.gateway.application.route.management.route_grant_reads import (
    assert_actor_owns_route_by_id,
    list_grantable_teams_for_route_id,
    list_route_grants_for_route,
)
from domains.gateway.application.route.management.route_read_mappers import route_row_to_api_dict
from domains.gateway.presentation.model_list_query import ModelListQueryDep
from domains.gateway.presentation.schemas.common import (
    RouteCallableModelItem,
    RouteCallableModelListResponse,
    RouteCreate,
    RouteResponse,
    RouteUpdate,
)
from domains.gateway.presentation.schemas.route_grants import (
    RouteGrantableTeamResponse,
    RouteGrantAliasUpdateRequest,
    RouteGrantCreateRequest,
    RouteGrantResponse,
)
from domains.identity.domain.rbac import Role
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from domains.tenancy.application.team_service import TeamService
from libs.api.pagination import build_page
from libs.db.database import get_db

from ._common import MgmtReads, MgmtWrites

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _personal_team_id(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    personal = await TeamService(db).ensure_personal_team(user_id)
    return personal.id


@router.get("/my-route-callable-models", response_model=RouteCallableModelListResponse)
async def list_my_route_callable_models(
    current_user: RequiredAuthUser,
    db: DbSession,
    query: ModelListQueryDep,
    team_id: Annotated[uuid.UUID | None, Query(description="按归属团队 tenant_id 筛选")] = None,
) -> RouteCallableModelListResponse:
    """列出当前用户可用于 personal 虚拟路由的 callable 模型（含跨团队协作团队）。"""
    is_platform_admin = current_user.role == Role.ADMIN.value
    user_id = get_user_uuid(current_user)
    result = await list_personal_route_callable_models_for_actor(
        db,
        user_id=user_id,
        is_platform_admin=is_platform_admin,
        query=query,
        team_id=team_id,
    )
    items = [
        RouteCallableModelItem.model_validate(route_callable_model_to_response_dict(c))
        for c in result.items
    ]
    envelope = build_page(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
    return RouteCallableModelListResponse.model_validate(envelope.model_dump())


@router.get("/my-routes", response_model=list[RouteResponse])
async def list_my_routes(
    current_user: RequiredAuthUser,
    reads: MgmtReads,
    db: DbSession,
) -> list[RouteResponse]:
    user_id = get_user_uuid(current_user)
    personal_id = await _personal_team_id(db, user_id)
    routes = await reads.list_gateway_routes(personal_id, only_enabled=False)
    return [RouteResponse.model_validate(route_row_to_api_dict(r)) for r in routes]


@router.post("/my-routes", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_my_route(
    body: RouteCreate,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
    db: DbSession,
) -> RouteResponse:
    user_id = get_user_uuid(current_user)
    is_platform_admin = current_user.role == Role.ADMIN.value
    personal_id = await _personal_team_id(db, user_id)
    route = await writes.create_gateway_route(
        tenant_id=personal_id,
        virtual_model=body.virtual_model,
        primary_models=body.primary_models,
        fallbacks_general=body.fallbacks_general,
        fallbacks_content_policy=body.fallbacks_content_policy,
        fallbacks_context_window=body.fallbacks_context_window,
        strategy=body.strategy.value,
        retry_policy=body.retry_policy,
        actor_user_id=user_id,
        actor_is_platform_admin=is_platform_admin,
    )
    return RouteResponse.model_validate(route_row_to_api_dict(route))


@router.patch("/my-routes/{route_id}", response_model=RouteResponse)
async def update_my_route(
    route_id: uuid.UUID,
    body: RouteUpdate,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
    db: DbSession,
) -> RouteResponse:
    user_id = get_user_uuid(current_user)
    is_platform_admin = current_user.role == Role.ADMIN.value
    personal_id = await _personal_team_id(db, user_id)
    updated = await writes.update_gateway_route(
        route_id,
        tenant_id=personal_id,
        fields=body.model_dump(exclude_unset=True),
        actor_user_id=user_id,
        actor_is_platform_admin=is_platform_admin,
    )
    return RouteResponse.model_validate(route_row_to_api_dict(updated))


@router.delete("/my-routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_route(
    route_id: uuid.UUID,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
    db: DbSession,
) -> None:
    user_id = get_user_uuid(current_user)
    personal_id = await _personal_team_id(db, user_id)
    await writes.delete_gateway_route(route_id, tenant_id=personal_id)


async def _assert_route_owned_by(db: AsyncSession, route_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await assert_actor_owns_route_by_id(db, route_id, user_id)


@router.get("/my-routes/{route_id}/grants", response_model=list[RouteGrantResponse])
async def list_my_route_grants(
    route_id: uuid.UUID,
    current_user: RequiredAuthUser,
    db: DbSession,
) -> list[RouteGrantResponse]:
    """列出该路由的全部跨团队共享授权（仅路由创建者）。"""
    user_id = get_user_uuid(current_user)
    await _assert_route_owned_by(db, route_id, user_id)
    return await list_route_grants_for_route(db, route_id)


@router.post(
    "/my-routes/{route_id}/grants",
    response_model=RouteGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_my_route_to_team(
    route_id: uuid.UUID,
    body: RouteGrantCreateRequest,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
    db: DbSession,
) -> RouteGrantResponse:
    """把路由发布给团队（仅路由创建者；委派模式，调用以 owner 身份解析底层模型）。"""
    user_id = get_user_uuid(current_user)
    grant = await writes.grant_route_to_team(
        route_id=route_id,
        target_tenant_id=body.target_tenant_id,
        exposed_alias=body.exposed_alias,
        actor_user_id=user_id,
    )
    grants = await list_route_grants_for_route(db, route_id)
    return next((g for g in grants if g.tenant_id == grant.tenant_id), grants[0])


@router.patch(
    "/my-routes/{route_id}/grants/{tenant_id}",
    response_model=RouteGrantResponse,
)
async def update_my_route_grant_alias(
    route_id: uuid.UUID,
    tenant_id: uuid.UUID,
    body: RouteGrantAliasUpdateRequest,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
    db: DbSession,
) -> RouteGrantResponse:
    user_id = get_user_uuid(current_user)
    grant = await writes.update_route_grant_alias(
        route_id=route_id,
        target_tenant_id=tenant_id,
        exposed_alias=body.exposed_alias,
        actor_user_id=user_id,
    )
    grants = await list_route_grants_for_route(db, route_id)
    return next((g for g in grants if g.tenant_id == grant.tenant_id), grants[0])


@router.delete(
    "/my-routes/{route_id}/grants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_my_route_grant(
    route_id: uuid.UUID,
    tenant_id: uuid.UUID,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
    db: DbSession,
) -> None:
    user_id = get_user_uuid(current_user)
    await writes.revoke_route_grant(
        route_id=route_id,
        target_tenant_id=tenant_id,
        actor_user_id=user_id,
        reason="owner_revoked",
    )


@router.get(
    "/my-routes/{route_id}/grantable-teams",
    response_model=list[RouteGrantableTeamResponse],
)
async def list_my_route_grantable_teams(
    route_id: uuid.UUID,
    current_user: RequiredAuthUser,
    db: DbSession,
) -> list[RouteGrantableTeamResponse]:
    user_id = get_user_uuid(current_user)
    personal_id = await _personal_team_id(db, user_id)
    return await list_grantable_teams_for_route_id(
        db,
        route_id=route_id,
        actor_user_id=user_id,
        fallback_route_tenant_id=personal_id,
    )
