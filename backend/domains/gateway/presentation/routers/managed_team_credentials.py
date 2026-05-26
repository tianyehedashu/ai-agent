"""Actor-scoped managed team credentials aggregate list."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.managed_team_credential_reads import (
    list_managed_team_credentials_for_actor,
)
from domains.gateway.presentation.credential_response import build_credential_response
from domains.gateway.presentation.schemas.common import ManagedTeamCredentialListResponse
from domains.identity.presentation.deps import ADMIN_ROLE, RequiredAuthUser, get_user_uuid
from libs.api.pagination import PageParams, page_query_params
from libs.db.database import get_db

from ._common import encryption_key

router = APIRouter()

PageDep = Annotated[PageParams, Depends(page_query_params)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/managed-team-credentials", response_model=ManagedTeamCredentialListResponse)
async def list_managed_team_credentials(
    current_user: RequiredAuthUser,
    db: DbSession,
    page: PageDep,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ManagedTeamCredentialListResponse:
    """列出当前用户可管理团队的 team-scope 凭据（跨团队聚合，分页）。"""
    is_platform_admin = current_user.role == ADMIN_ROLE
    enc_key = encryption_key()
    result = await list_managed_team_credentials_for_actor(
        db,
        user_id=get_user_uuid(current_user),
        is_platform_admin=is_platform_admin,
        page_params=page,
        search=search,
        encryption_key=enc_key,
    )
    return ManagedTeamCredentialListResponse(
        items=[
            build_credential_response(item, encryption_key=enc_key)
            for item in result.page.items
        ],
        total=result.page.total,
        page=result.page.page,
        page_size=result.page.page_size,
        has_next=result.page.has_next,
        has_prev=result.page.has_prev,
        queried_team_count=result.queried_team_count,
        queried_personal_team_count=result.queried_personal_team_count,
        queried_shared_team_count=result.queried_shared_team_count,
    )
