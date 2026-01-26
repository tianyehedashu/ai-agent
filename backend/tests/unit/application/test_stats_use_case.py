"""
Stats Use Case unit tests.
"""

import uuid

import pytest

from domains.agent.application import AgentUseCase, SessionUseCase
from domains.agent.application.stats_service import StatsService
from domains.identity.infrastructure.models.user import User
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


@pytest.mark.unit
class TestStatsService:
    """Stats Use Case tests."""

    @pytest.mark.asyncio
    async def test_get_system_stats(self, db_session):
        """Test: Get system statistics."""
        # Arrange
        stats_service = StatsService(db_session)

        # Create some test data.
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            hashed_password="hashed",
            name="Test User",
        )
        db_session.add(user)
        await db_session.flush()

        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            agent_service = AgentUseCase(db_session)
            await agent_service.create_agent(
                user_id=str(user.id),
                name="Test Agent",
                system_prompt="Test",
            )

            session_service = SessionUseCase(db_session)
            session = await session_service.create_session(user_id=str(user.id))

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
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_user_stats(self, db_session):
        """Test: Get user statistics."""
        # Arrange
        stats_service = StatsService(db_session)
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            hashed_password="hashed",
            name="Test User",
        )
        db_session.add(user)
        await db_session.flush()

        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            agent_service = AgentUseCase(db_session)
            await agent_service.create_agent(
                user_id=str(user.id),
                name="Test Agent",
                system_prompt="Test",
            )

            session_service = SessionUseCase(db_session)
            session = await session_service.create_session(user_id=str(user.id))

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
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_user_stats_empty(self, db_session):
        """Test: Get statistics for empty user."""
        # Arrange
        stats_service = StatsService(db_session)
        user = User(
            email=f"empty_{uuid.uuid4()}@example.com",
            hashed_password="hashed",
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
