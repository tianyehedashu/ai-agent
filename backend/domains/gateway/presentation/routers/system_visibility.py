"""PlatformAdmin：系统级凭据/模型可见性与 grants ACL。"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.catalog.management.system_visibility import (
    GatewaySystemVisibilityService,
)
from domains.gateway.domain.visibility.gateway_admin import assert_platform_admin
from domains.gateway.presentation.deps import CurrentTeam
from domains.gateway.presentation.routers._common import MgmtReads
from domains.gateway.presentation.schemas.common import (
    SystemGatewayGrantCreate,
    SystemGatewayGrantResponse,
    SystemGatewayGrantUpdate,
    SystemModelVisibilityPatch,
    SystemVisibilityPatch,
    SystemVisibilityTargetSnapshot,
)
from libs.db.database import get_db

router = APIRouter(prefix="/system", tags=["AI Gateway / System Visibility"])


def _visibility_svc(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewaySystemVisibilityService:
    return GatewaySystemVisibilityService(db)


def _require_platform_admin_team(team: CurrentTeam) -> None:
    assert_platform_admin(is_platform_admin=team.is_platform_admin)


def _grant_to_response(row: object) -> SystemGatewayGrantResponse:
    return SystemGatewayGrantResponse.model_validate(row)


@router.patch("/credentials/{credential_id}/visibility")
async def patch_credential_visibility(
    credential_id: uuid.UUID,
    body: SystemVisibilityPatch,
    team: CurrentTeam,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> dict[str, str]:
    _require_platform_admin_team(team)
    row = await svc.set_credential_visibility(
        credential_id,
        visibility=body.visibility,
        is_platform_admin=team.is_platform_admin,
    )
    return {"id": str(row.id), "visibility": row.visibility}


@router.patch("/models/{model_id}/visibility")
async def patch_model_visibility(
    model_id: uuid.UUID,
    body: SystemModelVisibilityPatch,
    team: CurrentTeam,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> dict[str, str]:
    _require_platform_admin_team(team)
    row = await svc.set_model_visibility(
        model_id,
        visibility=body.visibility,
        is_platform_admin=team.is_platform_admin,
    )
    return {"id": str(row.id), "visibility": row.visibility}


@router.get("/credentials/{credential_id}/grants", response_model=list[SystemGatewayGrantResponse])
async def list_credential_grants(
    credential_id: uuid.UUID,
    team: CurrentTeam,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> list[SystemGatewayGrantResponse]:
    _require_platform_admin_team(team)
    rows = await svc.list_grants_for_subject(
        "credential", credential_id, is_platform_admin=team.is_platform_admin
    )
    return [_grant_to_response(r) for r in rows]


@router.get("/models/{model_id}/grants", response_model=list[SystemGatewayGrantResponse])
async def list_model_grants(
    model_id: uuid.UUID,
    team: CurrentTeam,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> list[SystemGatewayGrantResponse]:
    _require_platform_admin_team(team)
    rows = await svc.list_grants_for_subject(
        "model", model_id, is_platform_admin=team.is_platform_admin
    )
    return [_grant_to_response(r) for r in rows]


@router.post(
    "/grants", response_model=SystemGatewayGrantResponse, status_code=status.HTTP_201_CREATED
)
async def create_grant(
    body: SystemGatewayGrantCreate,
    team: CurrentTeam,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> SystemGatewayGrantResponse:
    _require_platform_admin_team(team)
    row = await svc.create_grant(
        subject_kind=body.subject_kind,
        subject_id=body.subject_id,
        target_kind=body.target_kind,
        target_id=body.target_id,
        granted_by=team.user_id,
        note=body.note,
        is_platform_admin=team.is_platform_admin,
    )
    return _grant_to_response(row)


@router.patch("/grants/{grant_id}", response_model=SystemGatewayGrantResponse)
async def update_grant(
    grant_id: uuid.UUID,
    body: SystemGatewayGrantUpdate,
    team: CurrentTeam,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> SystemGatewayGrantResponse:
    _require_platform_admin_team(team)
    row = await svc.update_grant(
        grant_id,
        enabled=body.enabled,
        note=body.note,
        is_platform_admin=team.is_platform_admin,
    )
    return _grant_to_response(row)


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grant(
    grant_id: uuid.UUID,
    team: CurrentTeam,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> None:
    _require_platform_admin_team(team)
    await svc.delete_grant(grant_id, is_platform_admin=team.is_platform_admin)


admin_router = APIRouter(prefix="/admin", tags=["AI Gateway / System Visibility Admin"])


@admin_router.get(
    "/teams/{team_id}/system-visibility",
    response_model=SystemVisibilityTargetSnapshot,
)
async def team_system_visibility(
    team_id: uuid.UUID,
    team: CurrentTeam,
    reads: MgmtReads,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> SystemVisibilityTargetSnapshot:
    _require_platform_admin_team(team)
    grants = await svc.list_grants_for_target(
        "team", team_id, is_platform_admin=team.is_platform_admin
    )
    visible_names = await reads.list_callable_system_model_names(
        team_id,
        user_id=None,
    )
    return SystemVisibilityTargetSnapshot(
        target_kind="team",
        target_id=team_id,
        grants=[_grant_to_response(g) for g in grants],
        visible_model_names=visible_names,
    )


@admin_router.get(
    "/users/{user_id}/system-visibility",
    response_model=SystemVisibilityTargetSnapshot,
)
async def user_system_visibility(
    user_id: uuid.UUID,
    team: CurrentTeam,
    reads: MgmtReads,
    svc: Annotated[GatewaySystemVisibilityService, Depends(_visibility_svc)],
) -> SystemVisibilityTargetSnapshot:
    _require_platform_admin_team(team)
    personal_team_id = await reads.personal_team_id_for_user(user_id)
    grants = await svc.list_grants_for_target(
        "user", user_id, is_platform_admin=team.is_platform_admin
    )
    visible_names = await reads.list_callable_system_model_names(
        personal_team_id,
        user_id=user_id,
    )
    return SystemVisibilityTargetSnapshot(
        target_kind="user",
        target_id=user_id,
        grants=[_grant_to_response(g) for g in grants],
        visible_model_names=visible_names,
    )


__all__ = ["admin_router", "router"]
