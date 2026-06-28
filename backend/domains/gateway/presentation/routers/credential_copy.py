"""Actor-scoped credential copy across personal / team scopes."""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.domain.credential.credential_copy_policy import CredentialCopyScope
from domains.gateway.presentation.credential_import_response import (
    build_import_credentials_with_models_response,
)
from domains.gateway.presentation.routers._common import MgmtWrites, encryption_key
from domains.gateway.presentation.schemas.credential_import import (
    CopyCredentialsWithModelsRequest,
    ImportCredentialsWithModelsResponse,
)
from domains.identity.domain.policies.gateway_access_policy import assert_gateway_write_allowed
from domains.identity.domain.rbac import Role
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from domains.tenancy.application.management_team_resolve_use_case import (
    TenancyManagementTeamResolveUseCase,
)
from libs.db.database import get_db

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _resolve_team_role(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    platform_role: str,
    team_id: uuid.UUID,
) -> str:
    ctx = await TenancyManagementTeamResolveUseCase(session).resolve_management_team(
        user_id=user_id,
        platform_user_role=platform_role,
        x_team_id=None,
        path_team_id=str(team_id),
    )
    return ctx.team_role


@router.post(
    "/credentials/copy-with-models",
    response_model=ImportCredentialsWithModelsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def copy_credentials_with_models(
    body: CopyCredentialsWithModelsRequest,
    current_user: RequiredAuthUser,
    db: DbSession,
    writes: MgmtWrites,
) -> ImportCredentialsWithModelsResponse:
    """Copy credentials and associated models between personal and team scopes."""
    assert_gateway_write_allowed(current_user.role, "POST")
    user_id = get_user_uuid(current_user)
    is_platform_admin = current_user.role == Role.ADMIN.value

    source_scope = CredentialCopyScope(kind=body.source.kind, team_id=body.source.team_id)
    destination_scope = CredentialCopyScope(
        kind=body.destination.kind,
        team_id=body.destination.team_id,
    )

    source_team_role: str | None = None
    if source_scope.kind == "team" and source_scope.team_id is not None:
        source_team_role = await _resolve_team_role(
            db,
            user_id=user_id,
            platform_role=current_user.role,
            team_id=source_scope.team_id,
        )

    destination_team_role: str | None = None
    if destination_scope.kind == "team" and destination_scope.team_id is not None:
        destination_team_role = await _resolve_team_role(
            db,
            user_id=user_id,
            platform_role=current_user.role,
            team_id=destination_scope.team_id,
        )

    result = await writes.copy_credentials_with_models(
        credential_ids=body.credential_ids,
        source=source_scope,
        destination=destination_scope,
        actor_user_id=user_id,
        is_platform_admin=is_platform_admin,
        source_team_role=source_team_role,
        destination_team_role=destination_team_role,
    )
    return build_import_credentials_with_models_response(
        result, encryption_key=encryption_key()
    )


__all__ = ["router"]
