"""
Repository 权限过滤集成测试

测试 Repository 在实际数据库操作中的权限过滤功能。
"""


import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.agent import Agent
from domains.agent.infrastructure.models.session import Session
from domains.agent.infrastructure.repositories import (
    AgentRepository,
    SessionRepository,
)
from domains.identity.infrastructure.models.user import User
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


@pytest.mark.integration
class TestSessionRepositoryPermissions:
    """会话仓储权限过滤测试"""

    @pytest.mark.asyncio
    async def test_find_by_user_filters_by_permission_context(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试: find_by_user 根据权限上下文过滤"""
        # 创建两个用户的会话
        session1 = Session(
            user_id=test_user.id,
            title="User 1 Session",
            status="active",
            message_count=0,
            token_count=0,
        )
        db_session.add(session1)

        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()

        session2 = Session(
            user_id=other_user.id,
            title="User 2 Session",
            status="active",
            message_count=0,
            token_count=0,
        )
        db_session.add(session2)
        await db_session.commit()

        # 设置权限上下文为 test_user
        ctx = PermissionContext(user_id=test_user.id, role="user")
        set_permission_context(ctx)

        try:
            repository = SessionRepository(db_session)
            sessions = await repository.find_by_user()

            # 应该只返回 test_user 的会话
            assert len(sessions) == 1
            assert sessions[0].id == session1.id
            assert sessions[0].user_id == test_user.id
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_by_id_filters_by_permission_context(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试: get_by_id 根据权限上下文过滤"""
        # 创建其他用户的会话
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()

        other_session = Session(
            user_id=other_user.id,
            title="Other User Session",
            status="active",
            message_count=0,
            token_count=0,
        )
        db_session.add(other_session)
        await db_session.commit()

        # 设置权限上下文为 test_user
        ctx = PermissionContext(user_id=test_user.id, role="user")
        set_permission_context(ctx)

        try:
            repository = SessionRepository(db_session)
            session = await repository.get_by_id(other_session.id)

            # 应该返回 None（无权限）
            assert session is None
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_admin_can_access_all_sessions(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试: 管理员可以访问所有会话"""
        # 创建多个用户的会话
        session1 = Session(
            user_id=test_user.id,
            title="User 1 Session",
            status="active",
            message_count=0,
            token_count=0,
        )
        db_session.add(session1)

        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()

        session2 = Session(
            user_id=other_user.id,
            title="User 2 Session",
            status="active",
            message_count=0,
            token_count=0,
        )
        db_session.add(session2)
        await db_session.commit()

        # 设置权限上下文为管理员
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
            sessions = await repository.find_by_user()

            # 管理员应该能看到所有会话
            assert len(sessions) >= 2
            session_ids = {s.id for s in sessions}
            assert session1.id in session_ids
            assert session2.id in session_ids
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_anonymous_user_filters_by_anonymous_id(
        self, db_session: AsyncSession
    ):
        """测试: 匿名用户根据 anonymous_user_id 过滤"""
        anonymous_id1 = "anon-1"
        anonymous_id2 = "anon-2"

        session1 = Session(
            anonymous_user_id=anonymous_id1,
            title="Anon 1 Session",
            status="active",
            message_count=0,
            token_count=0,
        )
        db_session.add(session1)

        session2 = Session(
            anonymous_user_id=anonymous_id2,
            title="Anon 2 Session",
            status="active",
            message_count=0,
            token_count=0,
        )
        db_session.add(session2)
        await db_session.commit()

        # 设置权限上下文为匿名用户 1
        ctx = PermissionContext(anonymous_user_id=anonymous_id1, role="user")
        set_permission_context(ctx)

        try:
            repository = SessionRepository(db_session)
            sessions = await repository.find_by_user()

            # 应该只返回匿名用户 1 的会话
            assert len(sessions) == 1
            assert sessions[0].id == session1.id
            assert sessions[0].anonymous_user_id == anonymous_id1
        finally:
            clear_permission_context()


@pytest.mark.integration
class TestAgentRepositoryPermissions:
    """Agent 仓储权限过滤测试"""

    @pytest.mark.asyncio
    async def test_find_by_user_filters_by_permission_context(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试: find_by_user 根据权限上下文过滤"""
        # 创建两个用户的 Agent
        agent1 = Agent(
            user_id=test_user.id,
            name="User 1 Agent",
            system_prompt="Test",
        )
        db_session.add(agent1)

        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()

        agent2 = Agent(
            user_id=other_user.id,
            name="User 2 Agent",
            system_prompt="Test",
        )
        db_session.add(agent2)
        await db_session.commit()

        # 设置权限上下文为 test_user
        ctx = PermissionContext(user_id=test_user.id, role="user")
        set_permission_context(ctx)

        try:
            repository = AgentRepository(db_session)
            agents = await repository.find_by_user(test_user.id)

            # 应该只返回 test_user 的 Agent
            assert len(agents) == 1
            assert agents[0].id == agent1.id
            assert agents[0].user_id == test_user.id
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_admin_can_access_all_agents(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试: 管理员可以访问所有 Agent"""
        # 创建多个用户的 Agent
        agent1 = Agent(
            user_id=test_user.id,
            name="User 1 Agent",
            system_prompt="Test",
        )
        db_session.add(agent1)

        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()

        agent2 = Agent(
            user_id=other_user.id,
            name="User 2 Agent",
            system_prompt="Test",
        )
        db_session.add(agent2)
        await db_session.commit()

        # 设置权限上下文为管理员
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

            # 管理员应该能看到所有 Agent
            assert len(agents) >= 2
            agent_ids = {a.id for a in agents}
            assert agent1.id in agent_ids
            assert agent2.id in agent_ids
        finally:
            clear_permission_context()
