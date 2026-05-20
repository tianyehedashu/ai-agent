"""GatewayManagementWriteService 虚拟 Key 批量撤销。"""

from __future__ import annotations

import uuid

import pytest

from domains.agent.infrastructure.models.agent import Agent  # noqa: F401
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.virtual_key_service import generate_vkey
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.tenancy.application.team_service import TeamService


async def _create_vkey(
    db_session,
    *,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
) -> uuid.UUID:
    repo = VirtualKeyRepository(db_session)
    _, key_id_str, key_hash = generate_vkey()
    row = await repo.create(
        tenant_id=team_id,
        created_by_user_id=user_id,
        name=name,
        description=None,
        key_id_str=key_id_str,
        key_hash=key_hash,
        encrypted_key="encrypted",
        allowed_models=[],
        allowed_capabilities=[],
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=True,
    )
    await db_session.flush()
    return row.id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revoke_virtual_keys_batch_revokes_multiple(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)
    key_a = await _create_vkey(
        db_session, team_id=team.id, user_id=test_user.id, name="key-a"
    )
    key_b = await _create_vkey(
        db_session, team_id=team.id, user_id=test_user.id, name="key-b"
    )

    revoked, failed = await writes.revoke_virtual_keys_batch(
        [key_a, key_b],
        tenant_id=team.id,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
    )

    assert revoked == [key_a, key_b]
    assert failed == []
    repo = VirtualKeyRepository(db_session)
    assert (await repo.get(key_a)) is not None
    assert (await repo.get(key_a)).is_active is False
    assert (await repo.get(key_b)) is not None
    assert (await repo.get(key_b)).is_active is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revoke_virtual_keys_batch_reports_not_found(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)
    missing = uuid.uuid4()

    revoked, failed = await writes.revoke_virtual_keys_batch(
        [missing],
        tenant_id=team.id,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
    )

    assert revoked == []
    assert failed == [(missing, "not_found")]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revoke_virtual_keys_batch_reports_permission_denied(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)
    key_id = await _create_vkey(
        db_session, team_id=team.id, user_id=test_user.id, name="owner-key"
    )
    other_member = uuid.uuid4()

    revoked, failed = await writes.revoke_virtual_keys_batch(
        [key_id],
        tenant_id=team.id,
        actor_user_id=other_member,
        team_role="member",
        is_platform_admin=False,
    )

    assert revoked == []
    assert failed == [(key_id, "not_found")]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revoke_virtual_keys_batch_rejects_system_key(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    repo = VirtualKeyRepository(db_session)
    _, key_id_str, key_hash = generate_vkey()
    system_key = await repo.get_or_create_system_key(
        team.id,
        encrypted_key="enc-sys",
        key_hash=key_hash,
        key_id_str=key_id_str,
    )
    writes = GatewayManagementWriteService(db_session)

    revoked, failed = await writes.revoke_virtual_keys_batch(
        [system_key.id],
        tenant_id=team.id,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
    )

    assert revoked == []
    assert failed == [(system_key.id, "system_key")]
    refreshed = await repo.get(system_key.id)
    assert refreshed is not None
    assert refreshed.is_active is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_revoke_virtual_keys_batch_deduplicates_ids(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)
    key_id = await _create_vkey(
        db_session, team_id=team.id, user_id=test_user.id, name="dup-key"
    )

    revoked, failed = await writes.revoke_virtual_keys_batch(
        [key_id, key_id],
        tenant_id=team.id,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
    )

    assert revoked == [key_id]
    assert failed == []
