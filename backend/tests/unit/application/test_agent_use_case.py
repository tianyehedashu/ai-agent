"""
Agent Use Case unit tests.
"""

import uuid

import pytest

from domains.agent.application.agent_use_case import AgentUseCase
from domains.identity.infrastructure.models.user import User
from exceptions import NotFoundError
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


@pytest.mark.unit
class TestAgentUseCase:
    """Agent Use Case tests."""

    async def _create_test_user(self, db_session) -> User:
        """Helper function to create test user."""
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Test User",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_create_agent(self, db_session):
        """Test: Create agent."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = AgentUseCase(db_session)
        user_id = str(user.id)

        # Act
        agent = await use_case.create_agent(
            user_id=user_id,
            name="Test Agent",
            system_prompt="You are a helpful assistant.",
        )

        # Assert
        assert agent.id is not None
        assert agent.name == "Test Agent"
        assert agent.system_prompt == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_get_agent(self, db_session):
        """Test: Get agent by ID."""
        # Arrange
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = AgentUseCase(db_session)
            user_id = str(user.id)
            agent = await use_case.create_agent(
                user_id=user_id,
                name="Test Agent",
                system_prompt="You are a helpful assistant.",
            )

            # Act
            found = await use_case.get_agent(str(agent.id))

            # Assert
            assert found is not None
            assert found.id == agent.id
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, db_session):
        """Test: Get non-existent agent."""
        # Arrange
        use_case = AgentUseCase(db_session)

        # Act
        found = await use_case.get_agent(str(uuid.uuid4()))

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_list_agents(self, db_session):
        """Test: List user's agents."""
        # Arrange
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = AgentUseCase(db_session)
            user_id = str(user.id)

            await use_case.create_agent(
                user_id=user_id,
                name="Agent 1",
                system_prompt="Prompt 1",
            )
            await use_case.create_agent(
                user_id=user_id,
                name="Agent 2",
                system_prompt="Prompt 2",
            )

            # Act
            agents = await use_case.list_agents(user_id)

            # Assert
            assert len(agents) >= 2
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_update_agent(self, db_session):
        """Test: Update agent."""
        # Arrange
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = AgentUseCase(db_session)
            user_id = str(user.id)
            agent = await use_case.create_agent(
                user_id=user_id,
                name="Original Name",
                system_prompt="Original prompt",
            )

            # Act
            updated = await use_case.update_agent(
                agent_id=str(agent.id),
                name="Updated Name",
                description="New description",
            )

            # Assert
            assert updated.name == "Updated Name"
            assert updated.description == "New description"
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_delete_agent(self, db_session):
        """Test: Delete agent."""
        # Arrange
        user = await self._create_test_user(db_session)
        ctx = PermissionContext(user_id=user.id, role="user")
        set_permission_context(ctx)
        try:
            use_case = AgentUseCase(db_session)
            user_id = str(user.id)
            agent = await use_case.create_agent(
                user_id=user_id,
                name="To Delete",
                system_prompt="Prompt",
            )

            # Act
            await use_case.delete_agent(str(agent.id))

            # Assert
            found = await use_case.get_agent(str(agent.id))
            assert found is None
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self, db_session):
        """Test: Delete non-existent agent raises exception."""
        # Arrange
        use_case = AgentUseCase(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await use_case.delete_agent(str(uuid.uuid4()))
