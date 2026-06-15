"""Actor-scoped model subset copy to another team."""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.model_copy_types import (
    ModelCopyCredentialPlan,
)
from domains.gateway.presentation.routers._common import MgmtWrites
from domains.gateway.presentation.schemas.model_copy import (
    CopyModelsToTeamRequest,
    CopyModelsToTeamResponse,
    ModelCopyFailureItem,
    ModelCopySuccessItem,
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
    "/models/copy-to-team",
    response_model=CopyModelsToTeamResponse,
    status_code=status.HTTP_200_OK,
)
async def copy_models_to_team(
    body: CopyModelsToTeamRequest,
    current_user: RequiredAuthUser,
    db: DbSession,
    writes: MgmtWrites,
    response: Response,
) -> CopyModelsToTeamResponse:
    """Copy selected gateway_models rows to another team."""
    assert_gateway_write_allowed(current_user.role, "POST")
    user_id = get_user_uuid(current_user)
    is_platform_admin = current_user.role == Role.ADMIN.value

    destination_team_role = await _resolve_team_role(
        db,
        user_id=user_id,
        platform_role=current_user.role,
        team_id=body.destination_team_id,
    )

    plans = [
        ModelCopyCredentialPlan(
            source_credential_id=plan.source_credential_id,
            mode=plan.mode,
            destination_credential_id=plan.destination_credential_id,
        )
        for plan in body.credential_plans
    ]

    result = await writes.copy_models_to_team(
        model_ids=body.model_ids,
        destination_team_id=body.destination_team_id,
        credential_plans=plans,
        actor_user_id=user_id,
        is_platform_admin=is_platform_admin,
        destination_team_role=destination_team_role,
        platform_user_role=current_user.role,
    )

    response.status_code = (
        status.HTTP_201_CREATED if result.succeeded else status.HTTP_200_OK
    )

    return CopyModelsToTeamResponse(
        succeeded=[
            ModelCopySuccessItem(
                source_model_id=item.source_model_id,
                new_model_id=item.new_model_id,
                name=item.name,
            )
            for item in result.succeeded
        ],
        failed=[
            ModelCopyFailureItem(model_id=item.model_id, reason=item.reason)
            for item in result.failed
        ],
    )


__all__ = ["router"]
