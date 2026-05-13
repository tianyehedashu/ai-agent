"""
GatewayVirtualKeyRepository - CRUD/system 池/撤销 单元测试。
"""

from __future__ import annotations

import pytest

from domains.gateway.domain.virtual_key_service import generate_vkey
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.tenancy.application.team_service import TeamService


@pytest.mark.unit
class TestVirtualKeyRepository:
    @pytest.mark.asyncio
    async def test_create_then_get_by_hash(self, db_session, test_user):
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        repo = VirtualKeyRepository(db_session)
        plain, key_id, key_hash = generate_vkey()
        vk = await repo.create(
            team_id=team.id,
            created_by_user_id=test_user.id,
            name="test-key",
            description=None,
            key_id_str=key_id,
            key_hash=key_hash,
            encrypted_key="encrypted",
            allowed_models=[],
            allowed_capabilities=[],
            rpm_limit=60,
            tpm_limit=10_000,
            store_full_messages=True,
            guardrail_enabled=True,
        )
        await db_session.flush()

        found = await repo.get_by_hash(key_hash)
        assert found is not None
        assert found.id == vk.id
        assert found.name == "test-key"
        assert found.is_active is True
        assert found.is_system is False
        assert plain  # 只是确保返回了明文

    @pytest.mark.asyncio
    async def test_revoke_marks_inactive(self, db_session, test_user):
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        repo = VirtualKeyRepository(db_session)
        _, key_id, key_hash = generate_vkey()
        vk = await repo.create(
            team_id=team.id,
            created_by_user_id=test_user.id,
            name="to-revoke",
            description=None,
            key_id_str=key_id,
            key_hash=key_hash,
            encrypted_key="encrypted",
            allowed_models=[],
            allowed_capabilities=[],
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=False,
            guardrail_enabled=False,
        )
        ok = await repo.revoke(vk.id)
        assert ok is True
        refreshed = await repo.get(vk.id)
        assert refreshed is not None
        assert refreshed.is_active is False

    @pytest.mark.asyncio
    async def test_system_key_pool_idempotent(self, db_session, test_user):
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        repo = VirtualKeyRepository(db_session)
        _, key_id_a, hash_a = generate_vkey()
        first = await repo.get_or_create_system_key(
            team.id, encrypted_key="enc-a", key_hash=hash_a, key_id_str=key_id_a
        )
        # 第二次再创建应返回同一条
        _, key_id_b, hash_b = generate_vkey()
        second = await repo.get_or_create_system_key(
            team.id, encrypted_key="enc-b", key_hash=hash_b, key_id_str=key_id_b
        )
        assert first.id == second.id
        assert first.is_system is True

    @pytest.mark.asyncio
    async def test_list_excludes_system_by_default(self, db_session, test_user):
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        repo = VirtualKeyRepository(db_session)

        _, k1, h1 = generate_vkey()
        await repo.create(
            team_id=team.id,
            created_by_user_id=test_user.id,
            name="user-key",
            description=None,
            key_id_str=k1,
            key_hash=h1,
            encrypted_key="enc",
            allowed_models=[],
            allowed_capabilities=[],
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=True,
            guardrail_enabled=True,
        )
        _, k2, h2 = generate_vkey()
        await repo.get_or_create_system_key(
            team.id, encrypted_key="enc-sys", key_hash=h2, key_id_str=k2
        )

        items_no_sys = await repo.list_by_team(team.id)
        assert all(not v.is_system for v in items_no_sys)

        items_with_sys = await repo.list_by_team(team.id, include_system=True)
        assert any(v.is_system for v in items_with_sys)
