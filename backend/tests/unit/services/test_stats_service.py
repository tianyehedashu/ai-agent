"""
Stats Service 单元测试
"""

import pytest

from models.user import User
from services.agent import AgentService
from services.session import SessionService
from services.stats import StatsService


@pytest.mark.unit
class TestStatsService:
    """Stats Service 测试"""

    @pytest.mark.asyncio
    async def test_get_system_stats(self, db_session):
        """测试: 获取系统统计信息"""
        # Arrange
        stats_service = StatsService(db_session)

        # 创建一些测试数据
        user = User(
            email="test@example.com",
            password_hash="hashed",
            name="Test User",
        )
        db_session.add(user)
        await db_session.flush()

        agent_service = AgentService(db_session)
        await agent_service.create(
            user_id=str(user.id),
            name="Test Agent",
            system_prompt="Test",
        )

        session_service = SessionService(db_session)
        session = await session_service.create(user_id=str(user.id))

        await session_service.add_message(
            session_id=str(session.id),
            role="user",
            content="Test message",
        )

        await db_session.commit()

        # Act
        stats = await stats_service.get_system_stats()

        # Assert
        assert "total_users" in stats
        assert "total_agents" in stats
        assert "total_sessions" in stats
        assert "total_messages" in stats
        assert "active_sessions_today" in stats
        assert stats["total_users"] >= 1
        assert stats["total_agents"] >= 1
        assert stats["total_sessions"] >= 1
        assert stats["total_messages"] >= 1

    @pytest.mark.asyncio
    async def test_get_user_stats(self, db_session):
        """测试: 获取用户统计信息"""
        # Arrange
        stats_service = StatsService(db_session)
        user = User(
            email="test@example.com",
            password_hash="hashed",
            name="Test User",
        )
        db_session.add(user)
        await db_session.flush()

        agent_service = AgentService(db_session)
        await agent_service.create(
            user_id=str(user.id),
            name="Test Agent",
            system_prompt="Test",
        )

        session_service = SessionService(db_session)
        session = await session_service.create(user_id=str(user.id))

        await session_service.add_message(
            session_id=str(session.id),
            role="user",
            content="Test message",
            token_count=100,
        )

        await db_session.commit()

        # Act
        stats = await stats_service.get_user_stats(str(user.id))

        # Assert
        assert "agent_count" in stats
        assert "session_count" in stats
        assert "message_count" in stats
        assert "total_tokens" in stats
        assert stats["agent_count"] >= 1
        assert stats["session_count"] >= 1
        assert stats["message_count"] >= 1
        assert stats["total_tokens"] >= 100

    @pytest.mark.asyncio
    async def test_get_user_stats_empty(self, db_session):
        """测试: 获取空用户的统计信息"""
        # Arrange
        stats_service = StatsService(db_session)
        user = User(
            email="empty@example.com",
            password_hash="hashed",
            name="Empty User",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.commit()

        # Act
        stats = await stats_service.get_user_stats(str(user.id))

        # Assert
        assert stats["agent_count"] == 0
        assert stats["session_count"] == 0
        assert stats["message_count"] == 0
        assert stats["total_tokens"] == 0
