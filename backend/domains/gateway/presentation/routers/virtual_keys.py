"""Virtual Keys 子 router。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from fastapi import APIRouter, status

from domains.gateway.application.management.virtual_key_read_mappers import (
    virtual_key_from_orm,
)
from domains.gateway.domain.virtual_key_service import generate_vkey
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamMember,
)
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    VirtualKeyBatchRevokeFailureItem,
    VirtualKeyBatchRevokeRequest,
    VirtualKeyBatchRevokeResponse,
    VirtualKeyCreate,
    VirtualKeyCreateResponse,
    VirtualKeyResponse,
    VirtualKeyRevealResponse,
)
from libs.crypto import encrypt_value
from libs.exceptions import HttpMappableDomainError

from ._common import (
    MgmtReads,
    MgmtWrites,
    decrypt_vkey_for_reveal,
    encryption_key,
    vkey_to_response,
)

router = APIRouter()


@router.get("/keys", response_model=list[VirtualKeyResponse])
async def list_keys(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[VirtualKeyResponse]:
    keys = await reads.list_virtual_keys_for_team(
        team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )
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
        tenant_id=team.team_id,
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
    base = vkey_to_response(virtual_key_from_orm(record)).model_dump()
    return VirtualKeyCreateResponse(**base, plain_key=plain)


@router.get("/keys/{key_id}/reveal", response_model=VirtualKeyRevealResponse)
async def reveal_key(
    key_id: uuid.UUID,
    team: RequiredTeamMember,
    reads: MgmtReads,
) -> VirtualKeyRevealResponse:
    """解密并返回当前用户可见 vkey 的完整明文（与 revoke 同权限模型）。"""
    try:
        record = await reads.get_virtual_key_for_team_member(
            key_id,
            tenant_id=team.team_id,
            actor_user_id=team.user_id,
            team_role=team.team_role,
            is_platform_admin=team.is_platform_admin,
        )
        plain = decrypt_vkey_for_reveal(record, encryption_key=encryption_key())
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return VirtualKeyRevealResponse(plain_key=plain)


@router.post("/keys/revoke-batch", response_model=VirtualKeyBatchRevokeResponse)
async def revoke_keys_batch(
    body: VirtualKeyBatchRevokeRequest,
    team: RequiredTeamMember,
    writes: MgmtWrites,
) -> VirtualKeyBatchRevokeResponse:
    revoked, failed = await writes.revoke_virtual_keys_batch(
        body.key_ids,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )
    return VirtualKeyBatchRevokeResponse(
        revoked=revoked,
        failed=[
            VirtualKeyBatchRevokeFailureItem(key_id=key_id, reason=reason)
            for key_id, reason in failed
        ],
    )


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: uuid.UUID,
    team: RequiredTeamMember,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.revoke_virtual_key(
            key_id,
            tenant_id=team.team_id,
            actor_user_id=team.user_id,
            team_role=team.team_role,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


__all__ = ["router"]
