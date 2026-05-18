"""Virtual Keys 子 router。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from fastapi import APIRouter, status

from domains.gateway.domain.virtual_key_service import generate_vkey
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamMember,
)
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    VirtualKeyCreate,
    VirtualKeyCreateResponse,
    VirtualKeyResponse,
)
from libs.crypto import encrypt_value
from libs.exceptions import HttpMappableDomainError

from ._common import (
    MgmtReads,
    MgmtWrites,
    encryption_key,
    vkey_to_response,
)

router = APIRouter()


@router.get("/keys", response_model=list[VirtualKeyResponse])
async def list_keys(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[VirtualKeyResponse]:
    keys = await reads.list_virtual_keys_for_team(team.team_id)
    return [vkey_to_response(k) for k in keys]


@router.post("/keys", response_model=VirtualKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: VirtualKeyCreate,
    team: RequiredTeamMember,
    writes: MgmtWrites,
) -> VirtualKeyCreateResponse:
    plain, key_id_str, key_hash = generate_vkey()
    encrypted = encrypt_value(plain, encryption_key())
    expires_at = (
        datetime.now(UTC) + timedelta(days=body.expires_in_days) if body.expires_in_days else None
    )
    record = await writes.create_virtual_key(
        team_id=team.team_id,
        created_by_user_id=team.user_id,
        name=body.name,
        description=body.description,
        key_id_str=key_id_str,
        key_hash=key_hash,
        encrypted_key=encrypted,
        allowed_models=body.allowed_models,
        allowed_capabilities=body.allowed_capabilities,
        rpm_limit=body.rpm_limit,
        tpm_limit=body.tpm_limit,
        store_full_messages=body.store_full_messages,
        guardrail_enabled=body.guardrail_enabled,
        expires_at=expires_at,
    )
    base = vkey_to_response(record).model_dump()
    return VirtualKeyCreateResponse(**base, plain_key=plain)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: uuid.UUID,
    team: RequiredTeamMember,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.revoke_virtual_key(
            key_id,
            team_id=team.team_id,
            actor_user_id=team.user_id,
            team_role=team.team_role,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


__all__ = ["router"]
