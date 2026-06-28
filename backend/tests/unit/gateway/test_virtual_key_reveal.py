"""GatewayManagementReadService.get_virtual_key_for_team_member 权限语义。"""

from __future__ import annotations

import uuid

import pytest

from domains.agent.infrastructure.models.agent import Agent  # noqa: F401
from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.domain.errors import (
    SystemVirtualKeyForbiddenError,
    VirtualKeyNotFoundError,
)
from domains.gateway.domain.vkey.virtual_key_service import generate_vkey
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


async def _create_vkey(
    db_session,
    *,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str = "k",
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
        encrypted_key="enc",
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
async def test_get_virtual_key_returns_record_for_owner(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    key_id = await _create_vkey(db_session, team_id=team.id, user_id=test_user.id)
    reads = GatewayManagementReadService(db_session)

    record = await reads.get_virtual_key_for_team_member(
        key_id,
        tenant_id=team.id,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
    )

    assert record.id == key_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_virtual_key_missing_raises_not_found(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    reads = GatewayManagementReadService(db_session)
    missing = uuid.uuid4()

    with pytest.raises(VirtualKeyNotFoundError):
        await reads.get_virtual_key_for_team_member(
            missing,
            tenant_id=team.id,
            actor_user_id=test_user.id,
            team_role="owner",
            is_platform_admin=False,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_virtual_key_rejects_system_key(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    repo = VirtualKeyRepository(db_session)
    _, key_id_str, key_hash = generate_vkey()
    system_key = await repo.get_or_create_system_key(
        team.id, encrypted_key="enc", key_hash=key_hash, key_id_str=key_id_str
    )
    reads = GatewayManagementReadService(db_session)

    with pytest.raises(SystemVirtualKeyForbiddenError):
        await reads.get_virtual_key_for_team_member(
            system_key.id,
            tenant_id=team.id,
            actor_user_id=test_user.id,
            team_role="owner",
            is_platform_admin=False,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_virtual_key_non_creator_cannot_read(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    key_id = await _create_vkey(db_session, team_id=team.id, user_id=test_user.id)
    reads = GatewayManagementReadService(db_session)
    other_member = uuid.uuid4()

    with pytest.raises(VirtualKeyNotFoundError):
        await reads.get_virtual_key_for_team_member(
            key_id,
            tenant_id=team.id,
            actor_user_id=other_member,
            team_role="member",
            is_platform_admin=False,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_virtual_key_rejects_inactive(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    key_id = await _create_vkey(db_session, team_id=team.id, user_id=test_user.id)
    repo = VirtualKeyRepository(db_session)
    await repo.revoke(key_id)
    reads = GatewayManagementReadService(db_session)

    with pytest.raises(VirtualKeyNotFoundError):
        await reads.get_virtual_key_for_team_member(
            key_id,
            tenant_id=team.id,
            actor_user_id=test_user.id,
            team_role="owner",
            is_platform_admin=False,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_virtual_keys_member_sees_only_own(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    owner_id = test_user.id
    other_user = User(
        email=f"other_{uuid.uuid4()}@example.com",
        hashed_password="hashed_password",
        name="Other User",
    )
    db_session.add(other_user)
    await db_session.flush()
    member_id = other_user.id
    own_id = await _create_vkey(db_session, team_id=team.id, user_id=owner_id, name="own")
    other_id = await _create_vkey(db_session, team_id=team.id, user_id=member_id, name="other")
    reads = GatewayManagementReadService(db_session)

    as_owner = await reads.list_virtual_keys_for_team(
        team.id,
        actor_user_id=owner_id,
        team_role="owner",
        is_platform_admin=False,
    )
    assert {k.id for k in as_owner} == {own_id}

    as_member = await reads.list_virtual_keys_for_team(
        team.id,
        actor_user_id=member_id,
        team_role="member",
        is_platform_admin=False,
    )
    assert {k.id for k in as_member} == {other_id}
