"""virtual_key_team_grant_reads 单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.management.virtual_key_team_grant_reads import (
    list_active_grant_tenant_ids,
    list_active_grants_for_vkey,
    list_grantable_teams_for_actor,
)
from domains.gateway.application.management.virtual_key_team_grant_writes import (
    ensure_self_grant_for_vkey,
    grant_vkey_to_teams,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


async def _create_vkey(db_session, *, tenant_id: uuid.UUID, user_id: uuid.UUID):
    from bootstrap.config import settings

    repo = VirtualKeyRepository(db_session)
    key_id = uuid.uuid4().hex[:16]
    record = await repo.create(
        tenant_id=tenant_id,
        created_by_user_id=user_id,
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
    )
    await ensure_self_grant_for_vkey(
        db_session,
        vkey_id=record.id,
        tenant_id=tenant_id,
        granted_by_user_id=user_id,
    )
    return record


@pytest.mark.asyncio
async def test_list_active_grants_includes_self(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    vkey = await _create_vkey(db_session, tenant_id=team.id, user_id=test_user.id)
    grants = await list_active_grants_for_vkey(db_session, vkey.id)
    assert len(grants) == 1
    assert grants[0].is_self is True
    assert grants[0].tenant_id == team.id


@pytest.mark.asyncio
async def test_list_active_grant_tenant_ids(db_session, test_user) -> None:
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
    ids = await list_active_grant_tenant_ids(db_session, vkey.id)
    assert set(ids) == {primary.id, shared.id}


@pytest.mark.asyncio
async def test_list_grantable_teams_excludes_self_and_existing(db_session, test_user) -> None:
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    vkey = await _create_vkey(db_session, tenant_id=primary.id, user_id=test_user.id)
    existing = {primary.id}
    rows = await list_grantable_teams_for_actor(
        db_session,
        actor_user_id=test_user.id,
        vkey_tenant_id=primary.id,
        existing_grant_tenant_ids=existing,
    )
    team_ids = {row[0] for row in rows}
    assert shared.id in team_ids
    assert primary.id not in team_ids
