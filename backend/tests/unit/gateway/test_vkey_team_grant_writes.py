"""virtual_key_team_grant_writes 单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.vkey.management.virtual_key_team_grant_writes import (
    ensure_self_grant_for_vkey,
    grant_vkey_to_teams,
    revoke_vkey_team_grant,
)
from domains.gateway.domain.errors import SystemVirtualKeyForbiddenError, VirtualKeyNotFoundError
from domains.gateway.domain.vkey.virtual_key_access import assert_virtual_key_accessible_by_actor
from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


async def _create_vkey(db_session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, is_system: bool = False):
    from bootstrap.config import settings

    repo = VirtualKeyRepository(db_session)
    key_id = uuid.uuid4().hex[:16]
    record = await repo.create(
        tenant_id=tenant_id,
        created_by_user_id=None if is_system else user_id,
        name=f"vkey-{uuid.uuid4().hex[:6]}",
        description=None,
        key_id_str=key_id,
        key_hash=key_id,
        encrypted_key=encrypt_value("sk-gw-test", derive_encryption_key(settings.secret_key.get_secret_value())),
        allowed_models=[],
        allowed_capabilities=["chat"],
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
        expires_at=None,
        is_system=is_system,
    )
    if not is_system:
        await ensure_self_grant_for_vkey(
            db_session,
            vkey_id=record.id,
            tenant_id=tenant_id,
            granted_by_user_id=user_id,
        )
    return record


@pytest.mark.asyncio
async def test_grant_idempotent(db_session, test_user) -> None:
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    vkey = await _create_vkey(db_session, tenant_id=primary.id, user_id=test_user.id)
    first = await grant_vkey_to_teams(
        db_session,
        vkey_id=vkey.id,
        vkey_tenant_id=primary.id,
        tenant_ids=[shared.id],
        granted_by_user_id=test_user.id,
    )
    second = await grant_vkey_to_teams(
        db_session,
        vkey_id=vkey.id,
        vkey_tenant_id=primary.id,
        tenant_ids=[shared.id],
        granted_by_user_id=test_user.id,
    )
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id


@pytest.mark.asyncio
async def test_grant_skips_self_tenant(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    vkey = await _create_vkey(db_session, tenant_id=team.id, user_id=test_user.id)
    out = await grant_vkey_to_teams(
        db_session,
        vkey_id=vkey.id,
        vkey_tenant_id=team.id,
        tenant_ids=[team.id],
        granted_by_user_id=test_user.id,
    )
    assert out == []


@pytest.mark.asyncio
async def test_non_owner_gets_not_found(db_session, test_user) -> None:
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    other_user_id = uuid.uuid4()
    vkey = await _create_vkey(db_session, tenant_id=primary.id, user_id=test_user.id)
    with pytest.raises(VirtualKeyNotFoundError):
        assert_virtual_key_accessible_by_actor(
            vkey,
            key_id=str(vkey.id),
            tenant_id=primary.id,
            actor_user_id=other_user_id,
        )


@pytest.mark.asyncio
async def test_system_vkey_forbidden(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    vkey = await _create_vkey(
        db_session, tenant_id=team.id, user_id=test_user.id, is_system=True
    )
    with pytest.raises(SystemVirtualKeyForbiddenError):
        assert_virtual_key_accessible_by_actor(
            vkey,
            key_id=str(vkey.id),
            tenant_id=team.id,
            actor_user_id=test_user.id,
        )


@pytest.mark.asyncio
async def test_revoke_grant(db_session, test_user) -> None:
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    vkey = await _create_vkey(db_session, tenant_id=primary.id, user_id=test_user.id)
    await grant_vkey_to_teams(
        db_session,
        vkey_id=vkey.id,
        vkey_tenant_id=primary.id,
        tenant_ids=[shared.id],
        granted_by_user_id=test_user.id,
    )
    ok = await revoke_vkey_team_grant(db_session, vkey_id=vkey.id, tenant_id=shared.id)
    assert ok is True
    ok_again = await revoke_vkey_team_grant(db_session, vkey_id=vkey.id, tenant_id=shared.id)
    assert ok_again is False
