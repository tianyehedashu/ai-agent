"""
GatewayVirtualKeyRepository - CRUD/system 池/撤销 单元测试。
"""

from __future__ import annotations

import uuid

import pytest

# 触发跨域 ORM mapper 注册，避免 User.relationships 引用 Agent 时 _check_configure 失败
from domains.agent.infrastructure.models import (  # noqa: F401  # isort:skip
    agent as _agent_model,
    memory as _memory_model,
    message as _message_model,
)
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
    async def test_partial_unique_index_rejects_second_active_system_row(
        self, db_session, test_user
    ):
        """部分唯一索引在 DB 层杜绝同一 team 出现第二条 active system vkey。

        过去并发 chat 启动时（标题生成 + 主流）会同时进入
        ``get_or_create_system_key``，写入两条 ``is_system && is_active`` 行；
        随后 ``scalar_one_or_none()`` 抛 ``MultipleResultsFound`` →
        ``GatewayBridge.chat_completion`` 异常 → 回退直连 LiteLLM →
        ``gateway_request_logs`` 失去 team/user/vkey 归因 → dashboard 永远是 0。

        根因修复在 schema 层：``uq_gateway_virtual_keys_team_id_active_system``
        部分唯一索引（``20260513_uvk`` migration）让重复行根本无法 commit。
        """
        from sqlalchemy.exc import IntegrityError

        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        repo = VirtualKeyRepository(db_session)

        _, key_id_a, hash_a = generate_vkey()
        primary = await repo.get_or_create_system_key(
            team.id, encrypted_key="enc-a", key_hash=hash_a, key_id_str=key_id_a
        )

        async with db_session.begin_nested():
            _, key_id_b, hash_b = generate_vkey()
            with pytest.raises(IntegrityError):
                await repo.create(
                    team_id=team.id,
                    created_by_user_id=None,
                    name="__system_internal_bridge__",
                    description="尝试直接造重复行",
                    key_id_str=key_id_b,
                    key_hash=hash_b,
                    encrypted_key="enc-b",
                    allowed_models=[],
                    allowed_capabilities=[],
                    rpm_limit=None,
                    tpm_limit=None,
                    store_full_messages=False,
                    guardrail_enabled=True,
                    is_system=True,
                )

        # 主条目未受影响
        refreshed = await repo.get(primary.id)
        assert refreshed is not None
        assert refreshed.is_active is True
        assert refreshed.is_system is True

    @pytest.mark.asyncio
    async def test_concurrent_get_or_create_system_key_returns_single_row(
        self, db_session, test_user
    ):
        """并发两路 ``get_or_create_system_key`` 必须 upsert 到同一条 row。

        通过 PostgreSQL ``INSERT ... ON CONFLICT DO NOTHING`` 与 partial
        unique index 配合做真正幂等：先到的事务 INSERT 成功，后到的事务命中
        冲突变成 no-op，紧随其后的 SELECT 拿到同一主键。
        """
        import asyncio

        from sqlalchemy import select

        from domains.gateway.infrastructure.models.virtual_key import (
            GatewayVirtualKey,
        )

        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        repo = VirtualKeyRepository(db_session)

        async def _one() -> uuid.UUID:
            _, key_id, key_hash = generate_vkey()
            row = await repo.get_or_create_system_key(
                team.id,
                encrypted_key="enc",
                key_hash=key_hash,
                key_id_str=key_id,
            )
            return row.id

        ids = await asyncio.gather(*(_one() for _ in range(4)))
        assert len(set(ids)) == 1

        stmt = select(GatewayVirtualKey).where(
            GatewayVirtualKey.team_id == team.id,
            GatewayVirtualKey.is_system.is_(True),
            GatewayVirtualKey.is_active.is_(True),
        )
        active_rows = (await db_session.execute(stmt)).scalars().all()
        assert len(active_rows) == 1

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

    @pytest.mark.asyncio
    async def test_remove_model_names_from_allowed_lists(self, db_session, test_user):
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        repo = VirtualKeyRepository(db_session)
        _, k1, h1 = generate_vkey()
        await repo.create(
            team_id=team.id,
            created_by_user_id=test_user.id,
            name="prune-me",
            description=None,
            key_id_str=k1,
            key_hash=h1,
            encrypted_key="enc",
            allowed_models=["gone-model", "keep-model"],
            allowed_capabilities=[],
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=False,
            guardrail_enabled=False,
        )
        await db_session.flush()
        n = await repo.remove_model_names_from_all_allowed_lists(frozenset({"gone-model"}))
        assert n == 1
        found = await repo.get_by_hash(h1)
        assert found is not None
        assert found.allowed_models == ["keep-model"]
