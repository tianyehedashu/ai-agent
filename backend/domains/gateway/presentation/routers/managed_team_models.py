"""Actor-scoped managed team models aggregate list."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.managed_team_model_reads import (
    list_managed_team_models_for_actor,
)
from domains.gateway.presentation.gateway_model_list_response import (
    build_gateway_model_list_response,
)
from domains.gateway.presentation.model_list_query import ModelListQueryDep
from domains.gateway.presentation.schemas.common import ManagedTeamModelListResponse
from domains.identity.presentation.deps import ADMIN_ROLE, RequiredAuthUser, get_user_uuid
from libs.db.database import get_db

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/managed-team-models", response_model=ManagedTeamModelListResponse)
async def list_managed_team_models(
    current_user: RequiredAuthUser,
    db: DbSession,
    query: ModelListQueryDep,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ManagedTeamModelListResponse:
    """列出当前用户可管理团队的 team registry 模型（跨团队聚合，分页）。"""
    is_platform_admin = current_user.role == ADMIN_ROLE
    result = await list_managed_team_models_for_actor(
        db,
        user_id=get_user_uuid(current_user),
        is_platform_admin=is_platform_admin,
        query=query,
        search=search,
    )
    base = build_gateway_model_list_response(result.page)
    return ManagedTeamModelListResponse(
        **base.model_dump(),
        queried_team_count=result.queried_team_count,
        queried_personal_team_count=result.queried_personal_team_count,
        queried_shared_team_count=result.queried_shared_team_count,
        tenant_ids_with_models=list(result.tenant_ids_with_models),
    )
