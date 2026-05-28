"""
Repository 权限过滤集成测试

测试 Repository 在实际数据库操作中的权限过滤功能。
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.agent import Agent
from domains.agent.infrastructure.repositories import AgentRepository
from domains.identity.domain.anonymous_tenant import resolve_anonymous_tenant_id
from domains.identity.infrastructure.models.user import User
from domains.session.infrastructure.models import Session
from domains.session.infrastructure.repositories import SessionRepository
from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


async def _add_session_for_user(
    db_session: AsyncSession,
    user: User,
    *,
    title: str,
) -> tuple[Session, uuid.UUID]:
    tenant_id = await PersonalTeamProvisioner(db_session).ensure_personal_team(user.id)
    session = Session(
        tenant_id=tenant_id,
        title=title,
        status="active",
        message_count=0,
        token_count=0,
    )
    db_session.add(session)
    return session, tenant_id


async def _add_session_for_anonymous(
    db_session: AsyncSession,
    anonymous_cookie_id: str,
    *,
    title: str,
) -> tuple[Session, uuid.UUID]:
    tenant_id = resolve_anonymous_tenant_id(anonymous_cookie_id)
    session = Session(
        tenant_id=tenant_id,
        title=title,
        status="active",
        message_count=0,
        token_count=0,
    )
    db_session.add(session)
    return session, tenant_id


@pytest.mark.integration
class TestSessionRepositoryPermissions:
    """会话仓储权限过滤测试"""

    @pytest.mark.asyncio
    async def test_find_by_user_filters_by_permission_context(
        self, db_session: AsyncSession, test_user: User
    ):
        session1, tenant1 = await _add_session_for_user(
            db_session, test_user, title="User 1 Session"
        )

        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()
        await _add_session_for_user(db_session, other_user, title="User 2 Session")
        await db_session.commit()

        ctx = PermissionContext(
            user_id=test_user.id,
            role="user",
            team_ids=frozenset({tenant1}),
        )
        set_permission_context(ctx)

        try:
            repository = SessionRepository(db_session)
            sessions = await repository.find_by_user(user_id=test_user.id)

            assert len(sessions) == 1
            assert sessions[0].id == session1.id
            assert sessions[0].tenant_id == tenant1
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_by_id_filters_by_permission_context(
        self, db_session: AsyncSession, test_user: User
    ):
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()

        other_session, other_tenant = await _add_session_for_user(
            db_session, other_user, title="Other User Session"
        )
        user_tenant = await PersonalTeamProvisioner(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        ctx = PermissionContext(
            user_id=test_user.id,
            role="user",
            team_ids=frozenset({user_tenant}),
        )
        set_permission_context(ctx)

        try:
            repository = SessionRepository(db_session)
            session = await repository.get_by_id(other_session.id)
            assert session is None
            assert other_tenant not in {user_tenant}
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_admin_get_by_id_bypasses_tenant_list_scope(
        self, db_session: AsyncSession, test_user: User
    ):
        """平台 admin 可按 ID 读取任意会话；列表仍仅 personal tenant。"""
        session1, _ = await _add_session_for_user(db_session, test_user, title="User 1 Session")
        await db_session.commit()

        admin_user = User(
            email="admin@example.com",
            hashed_password="hashed",
            role="admin",
        )
        db_session.add(admin_user)
        await db_session.flush()

        ctx = PermissionContext(user_id=admin_user.id, role="admin")
        set_permission_context(ctx)

        try:
            repository = SessionRepository(db_session)
            assert await repository.get_by_id(session1.id) is not None
            listed = await repository.find_by_user(user_id=admin_user.id)
            assert session1.id not in {s.id for s in listed}
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_anonymous_user_filters_by_tenant(self, db_session: AsyncSession):
        anonymous_id1 = "anon-1"
        anonymous_id2 = "anon-2"

        session1, tenant1 = await _add_session_for_anonymous(
            db_session, anonymous_id1, title="Anon 1 Session"
        )
        await _add_session_for_anonymous(db_session, anonymous_id2, title="Anon 2 Session")
        await db_session.commit()

        ctx = PermissionContext(
            anonymous_user_id=anonymous_id1,
            role="user",
            team_ids=frozenset({tenant1}),
        )
        set_permission_context(ctx)

        try:
            repository = SessionRepository(db_session)
            sessions = await repository.find_by_user(anonymous_user_id=anonymous_id1)

            assert len(sessions) == 1
            assert sessions[0].id == session1.id
            assert sessions[0].tenant_id == tenant1
        finally:
            clear_permission_context()


async def _add_agent_for_user(
    db_session: AsyncSession,
    user: User,
    *,
    name: str,
) -> tuple[Agent, uuid.UUID]:
    tenant_id = await PersonalTeamProvisioner(db_session).ensure_personal_team(user.id)
    agent = Agent(
        tenant_id=tenant_id,
        name=name,
        system_prompt="Test",
    )
    db_session.add(agent)
    return agent, tenant_id


@pytest.mark.integration
class TestAgentRepositoryPermissions:
    """Agent 仓储权限过滤测试"""

    @pytest.mark.asyncio
    async def test_find_by_user_filters_by_permission_context(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试: find_by_user 根据权限上下文过滤"""
        agent1, tenant1 = await _add_agent_for_user(db_session, test_user, name="User 1 Agent")

        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()

        await _add_agent_for_user(db_session, other_user, name="User 2 Agent")
        await db_session.commit()

        ctx = PermissionContext(
            user_id=test_user.id,
            role="user",
            team_ids=frozenset({tenant1}),
        )
        set_permission_context(ctx)

        try:
            repository = AgentRepository(db_session)
            agents = await repository.find_by_user(test_user.id)

            assert len(agents) == 1
            assert agents[0].id == agent1.id
            assert agents[0].tenant_id == tenant1
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_admin_can_access_all_agents(self, db_session: AsyncSession, test_user: User):
        """测试: 管理员可以访问所有 Agent"""
        agent1, _ = await _add_agent_for_user(db_session, test_user, name="User 1 Agent")

        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()

        agent2, _ = await _add_agent_for_user(db_session, other_user, name="User 2 Agent")
        await db_session.commit()

        admin_user = User(
            email="admin@example.com",
            hashed_password="hashed",
            role="admin",
        )
        db_session.add(admin_user)
        await db_session.flush()

        ctx = PermissionContext(user_id=admin_user.id, role="admin")
        set_permission_context(ctx)

        try:
            repository = AgentRepository(db_session)
            agents = await repository.find_by_user(admin_user.id)

            assert len(agents) >= 2
            agent_ids = {a.id for a in agents}
            assert agent1.id in agent_ids
            assert agent2.id in agent_ids
        finally:
            clear_permission_context()
