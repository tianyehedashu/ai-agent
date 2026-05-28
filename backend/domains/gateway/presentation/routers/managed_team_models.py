"""Actor-scoped managed team models aggregate list."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.managed_team_model_credential_filter_reads import (
    list_managed_team_model_credential_filters_for_actor,
)
from domains.gateway.application.management.managed_team_model_reads import (
    list_managed_team_models_for_actor,
)
from domains.gateway.application.management.managed_team_model_usage_reads import (
    aggregate_managed_team_models_route_usage,
)
from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.domain.policies.model_selection import registry_kind_for_merged_row
from domains.gateway.presentation.gateway_model_list_response import (
    build_gateway_model_list_response,
)
from domains.gateway.presentation.gateway_usage_list_response import (
    build_managed_team_model_usage_summary_response,
)
from domains.gateway.presentation.managed_team_model_credential_filter_response import (
    build_managed_team_model_credential_filter_list_response,
)
from domains.gateway.presentation.model_list_query import ModelListQueryDep
from domains.gateway.presentation.schemas.common import (
    ManagedTeamModelCredentialFilterListResponse,
    ManagedTeamModelListResponse,
    ManagedTeamModelRouteUsageItem,
    ManagedTeamModelUsageSummaryResponse,
)
from domains.identity.presentation.deps import ADMIN_ROLE, RequiredAuthUser, get_user_uuid
from libs.api.pagination import PageParams, page_query_params
from libs.db.database import get_db

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
PageDep = Annotated[PageParams, Depends(page_query_params)]


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
    reads = GatewayManagementReadService(db)
    team_cred_ids = {
        row.credential_id
        for row in result.page.items
        if registry_kind_for_merged_row(row) == "team"
    }
    team_credentials_by_id = await reads.map_team_credentials_display_by_id(team_cred_ids)
    base = build_gateway_model_list_response(
        result.page,
        team_credentials_by_id=team_credentials_by_id,
    )
    return ManagedTeamModelListResponse(
        **base.model_dump(),
        queried_team_count=result.queried_team_count,
        queried_personal_team_count=result.queried_personal_team_count,
        queried_shared_team_count=result.queried_shared_team_count,
        tenant_ids_with_models=list(result.tenant_ids_with_models),
    )


@router.get(
    "/managed-team-model-credential-filters",
    response_model=ManagedTeamModelCredentialFilterListResponse,
)
async def list_managed_team_model_credential_filters(
    current_user: RequiredAuthUser,
    db: DbSession,
) -> ManagedTeamModelCredentialFilterListResponse:
    """跨协作团队注册模型绑定的凭据（筛选下拉；成员可见团队内模型所用凭据名）。"""
    is_platform_admin = current_user.role == ADMIN_ROLE
    result = await list_managed_team_model_credential_filters_for_actor(
        db,
        user_id=get_user_uuid(current_user),
        is_platform_admin=is_platform_admin,
    )
    return build_managed_team_model_credential_filter_list_response(result)


@router.get(
    "/managed-team-models/usage-summary",
    response_model=ManagedTeamModelUsageSummaryResponse,
)
async def managed_team_models_usage_summary(
    current_user: RequiredAuthUser,
    db: DbSession,
    page: PageDep,
    days: int = Query(7, ge=1, le=90),
    provider: str | None = Query(None, min_length=1, max_length=50),
    route_names: list[str] | None = Query(
        default=None,
        description="仅聚合指定 route；传入时忽略 page/page_size。",
    ),
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ManagedTeamModelUsageSummaryResponse:
    if route_names is not None and len(route_names) > 200:
        route_names = route_names[:200]
    is_platform_admin = current_user.role == ADMIN_ROLE
    items, total, start, end = await aggregate_managed_team_models_route_usage(
        db,
        user_id=get_user_uuid(current_user),
        is_platform_admin=is_platform_admin,
        days=days,
        provider=provider,
        route_names=route_names,
        team_search=search,
        page=page.page,
        page_size=page.page_size,
    )
    validated_items = [ManagedTeamModelRouteUsageItem.model_validate(i) for i in items]
    return build_managed_team_model_usage_summary_response(
        items=validated_items,
        total=total,
        page=page.page,
        page_size=page.page_size,
        start=start,
        end=end,
    )
