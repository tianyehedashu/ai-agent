"""virtual_key_grants.py — 跨团队 vkey 授权 router"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.virtual_key_team_grant_reads import (
    list_active_grants_for_vkey,
    list_grantable_team_responses,
    map_grants_to_responses,
)
from domains.gateway.application.management.virtual_key_team_grant_writes import (
    grant_vkey_to_teams,
    revoke_vkey_team_grant,
)
from domains.gateway.application.management.vkey_team_grant_policy import (
    assert_actor_member_of_vkey_grant_targets,
)
from domains.gateway.domain.errors import VirtualKeyNotFoundError
from domains.gateway.domain.virtual_key_access import assert_virtual_key_accessible_by_actor
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.gateway.presentation.deps import CurrentTeam, RequiredTeamMember
from domains.gateway.presentation.schemas.grants import (
    GrantableTeamResponse,
    VirtualKeyGrantBatchRequest,
    VirtualKeyTeamGrantResponse,
)
from libs.api.deps import get_db
from libs.exceptions import NotFoundError, ValidationError

router = APIRouter()


async def _load_vkey_or_404(
    db: AsyncSession,
    key_id: uuid.UUID,
    team_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
):
    """加载 vkey 并校验 actor 可见性（仅创建者本人）。"""
    repo = VirtualKeyRepository(db)
    record = await repo.get(key_id)
    if record is None or record.tenant_id != team_id:
        raise VirtualKeyNotFoundError(str(key_id))
    return assert_virtual_key_accessible_by_actor(
        record,
        key_id=str(key_id),
        tenant_id=team_id,
        actor_user_id=actor_user_id,
    )


@router.get("/keys/{key_id}/grants", response_model=list[VirtualKeyTeamGrantResponse])
async def list_grants(
    key_id: uuid.UUID,
    team: CurrentTeam,
    db: AsyncSession = Depends(get_db),
) -> list[VirtualKeyTeamGrantResponse]:
    """列出 vkey 的所有 active grant（含自洽行）。"""
    await _load_vkey_or_404(db, key_id, team.team_id, team.user_id)
    grants = await list_active_grants_for_vkey(db, key_id)
    return await map_grants_to_responses(db, grants)


@router.post(
    "/keys/{key_id}/grants",
    response_model=list[VirtualKeyTeamGrantResponse],
    status_code=status.HTTP_201_CREATED,
)
async def grant_to_teams(
    key_id: uuid.UUID,
    body: VirtualKeyGrantBatchRequest,
    team: RequiredTeamMember,
    db: AsyncSession = Depends(get_db),
) -> list[VirtualKeyTeamGrantResponse]:
    """幂等批量授权 vkey 到指定 team（仅 vkey 创建者可操作）。"""
    record = await _load_vkey_or_404(db, key_id, team.team_id, team.user_id)

    await assert_actor_member_of_vkey_grant_targets(
        db,
        actor_user_id=team.user_id,
        tenant_ids=body.tenant_ids,
    )

    grants = await grant_vkey_to_teams(
        db,
        vkey_id=key_id,
        vkey_tenant_id=record.tenant_id,
        tenant_ids=body.tenant_ids,
        granted_by_user_id=team.user_id,
    )
    return await map_grants_to_responses(db, grants)


@router.delete("/keys/{key_id}/grants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_grant(
    key_id: uuid.UUID,
    tenant_id: uuid.UUID,
    team: RequiredTeamMember,
    db: AsyncSession = Depends(get_db),
) -> None:
    """撤销一行 grant（is_self=TRUE 会被拒绝）。"""
    record = await _load_vkey_or_404(db, key_id, team.team_id, team.user_id)

    if tenant_id == record.tenant_id:
        raise ValidationError("Cannot revoke self-grant (bound team)")

    success = await revoke_vkey_team_grant(db, vkey_id=key_id, tenant_id=tenant_id)
    if not success:
        raise NotFoundError(f"Grant not found: vkey={key_id}, tenant={tenant_id}")


@router.get("/keys/{key_id}/grants/grantable-teams", response_model=list[GrantableTeamResponse])
async def list_grantable_teams(
    key_id: uuid.UUID,
    team: CurrentTeam,
    db: AsyncSession = Depends(get_db),
) -> list[GrantableTeamResponse]:
    """列出 actor 可作 grant 目标的 team（membership ∖ 已授权 ∖ 主属）。"""
    record = await _load_vkey_or_404(db, key_id, team.team_id, team.user_id)

    existing_grants = await list_active_grants_for_vkey(db, key_id)
    existing_tenant_ids = {g.tenant_id for g in existing_grants}

    return await list_grantable_team_responses(
        db,
        actor_user_id=team.user_id,
        vkey_tenant_id=record.tenant_id,
        existing_grant_tenant_ids=existing_tenant_ids,
    )


__all__ = ["router"]
