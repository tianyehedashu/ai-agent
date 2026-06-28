"""个人 BYOK 凭据/模型 → 协作团队授权 API。"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.grant.management.resource_grant_reads import (
    list_owner_grants,
    list_team_granted_models as fetch_team_granted_models,
)
from domains.gateway.application.grant.management.resource_grant_writes import (
    ResourceGrantWriteService,
)
from domains.gateway.presentation.schemas.resource_grants import (
    GrantedModelResponse,
    ResourceGrantCreateRequest,
    ResourceGrantResponse,
    ResourceGrantUpdateRequest,
)
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from libs.api.deps import get_db

router = APIRouter(tags=["AI Gateway / Resource Grants"])


def _grant_svc(db: Annotated[AsyncSession, Depends(get_db)]) -> ResourceGrantWriteService:
    return ResourceGrantWriteService(db)


@router.get("/resource-grants", response_model=list[ResourceGrantResponse])
async def list_my_resource_grants(
    user: RequiredAuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[ResourceGrantResponse]:
    """列出当前用户授权出去的资源 grant。"""
    rows = await list_owner_grants(db, get_user_uuid(user))
    return [ResourceGrantResponse.model_validate(row) for row in rows]


@router.post(
    "/resource-grants",
    response_model=list[ResourceGrantResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_resource_grants(
    body: ResourceGrantCreateRequest,
    user: RequiredAuthUser,
    svc: Annotated[ResourceGrantWriteService, Depends(_grant_svc)],
) -> list[ResourceGrantResponse]:
    if body.subject_kind == "credential":
        rows = await svc.grant_credential_to_teams(
            credential_id=body.subject_id,
            target_team_ids=body.target_team_ids,
            actor_user_id=get_user_uuid(user),
            note=body.note,
        )
    else:
        rows = await svc.grant_model_to_teams(
            model_id=body.subject_id,
            target_team_ids=body.target_team_ids,
            actor_user_id=get_user_uuid(user),
            note=body.note,
        )
    return [ResourceGrantResponse.model_validate(row) for row in rows]


@router.patch("/resource-grants/{grant_id}", response_model=ResourceGrantResponse)
async def patch_resource_grant(
    grant_id: uuid.UUID,
    body: ResourceGrantUpdateRequest,
    user: RequiredAuthUser,
    svc: Annotated[ResourceGrantWriteService, Depends(_grant_svc)],
) -> ResourceGrantResponse:
    row = await svc.update_grant(
        grant_id,
        actor_user_id=get_user_uuid(user),
        enabled=body.enabled,
        note=body.note,
    )
    return ResourceGrantResponse.model_validate(row)


@router.delete("/resource-grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource_grant(
    grant_id: uuid.UUID,
    user: RequiredAuthUser,
    svc: Annotated[ResourceGrantWriteService, Depends(_grant_svc)],
) -> None:
    await svc.revoke_grant(grant_id, actor_user_id=get_user_uuid(user))


@router.get(
    "/teams/{team_id}/granted-resources/models",
    response_model=list[GrantedModelResponse],
)
async def list_team_granted_models_endpoint(
    team_id: uuid.UUID,
    user: RequiredAuthUser,
    db: AsyncSession = Depends(get_db),
) -> list[GrantedModelResponse]:
    from domains.gateway.application.grant.management.resource_grant_policy import (
        assert_actor_member_of_team,
    )

    await assert_actor_member_of_team(db, actor_user_id=get_user_uuid(user), team_id=team_id)
    rows = await fetch_team_granted_models(db, team_id)
    return [
        GrantedModelResponse(
            model_id=row.model_id,
            name=row.name,
            real_model=row.real_model,
            provider=row.provider,
            capability=row.capability,
            credential_id=row.credential_id,
            owner_user_id=row.owner_user_id,
            personal_team_id=row.personal_team_id,
        )
        for row in rows
    ]


__all__ = ["router"]
