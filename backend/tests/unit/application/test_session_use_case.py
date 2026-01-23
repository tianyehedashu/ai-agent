"""
Session Use Case unit tests.
"""

import uuid

import pytest

from domains.identity.infrastructure.models.user import User
from domains.runtime.application.session_use_case import SessionUseCase
from domains.runtime.domain.entities.session import SessionOwner
from exceptions import NotFoundError


@pytest.mark.unit
class TestSessionUseCase:
    """Session Use Case tests."""

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
    async def test_create_session(self, db_session):
        """Test: Create session."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = SessionUseCase(db_session)

        # Act
        session = await use_case.create_session(
            user_id=str(user.id),
            title="Test Session",
        )

        # Assert
        assert session.id is not None
        assert session.user_id == user.id
        assert session.title == "Test Session"

    @pytest.mark.asyncio
    async def test_create_anonymous_session(self, db_session):
        """Test: Create anonymous session."""
        # Arrange
        use_case = SessionUseCase(db_session)
        anonymous_id = f"anon_{uuid.uuid4()}"

        # Act
        session = await use_case.create_session(
            anonymous_user_id=anonymous_id,
            title="Anonymous Session",
        )

        # Assert
        assert session.id is not None
        assert session.anonymous_user_id == anonymous_id
        assert session.user_id is None

    @pytest.mark.asyncio
    async def test_get_session(self, db_session):
        """Test: Get session by ID."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = SessionUseCase(db_session)
        session = await use_case.create_session(
            user_id=str(user.id),
            title="Test Session",
        )

        # Act
        found = await use_case.get_session(str(session.id))

        # Assert
        assert found is not None
        assert found.id == session.id

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, db_session):
        """Test: Get non-existent session."""
        # Arrange
        use_case = SessionUseCase(db_session)

        # Act
        found = await use_case.get_session(str(uuid.uuid4()))

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, db_session):
        """Test: List user's sessions."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = SessionUseCase(db_session)
        user_id = str(user.id)

        await use_case.create_session(
            user_id=user_id,
            title="Session 1",
        )
        await use_case.create_session(
            user_id=user_id,
            title="Session 2",
        )

        # Act
        sessions = await use_case.list_sessions(user_id=user_id)

        # Assert
        assert len(sessions) >= 2

    @pytest.mark.asyncio
    async def test_update_session(self, db_session):
        """Test: Update session."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = SessionUseCase(db_session)
        session = await use_case.create_session(
            user_id=str(user.id),
            title="Original Title",
        )

        # Act
        updated = await use_case.update_session(
            session_id=str(session.id),
            title="Updated Title",
        )

        # Assert
        assert updated.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_session(self, db_session):
        """Test: Delete session."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = SessionUseCase(db_session)
        session = await use_case.create_session(
            user_id=str(user.id),
            title="To Delete",
        )

        # Act
        await use_case.delete_session(str(session.id))

        # Assert
        found = await use_case.get_session(str(session.id))
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, db_session):
        """Test: Delete non-existent session raises exception."""
        # Arrange
        use_case = SessionUseCase(db_session)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await use_case.delete_session(str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_add_message(self, db_session):
        """Test: Add message to session."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = SessionUseCase(db_session)
        session = await use_case.create_session(
            user_id=str(user.id),
            title="Message Test",
        )

        # Act
        message = await use_case.add_message(
            session_id=str(session.id),
            role="user",
            content="Hello, world!",
        )

        # Assert
        assert message.id is not None
        assert message.role == "user"
        assert message.content == "Hello, world!"

    @pytest.mark.asyncio
    async def test_get_messages(self, db_session):
        """Test: Get session messages."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = SessionUseCase(db_session)
        session = await use_case.create_session(
            user_id=str(user.id),
            title="Message Test",
        )

        await use_case.add_message(
            session_id=str(session.id),
            role="user",
            content="User message",
        )
        await use_case.add_message(
            session_id=str(session.id),
            role="assistant",
            content="Assistant message",
        )

        # Act
        messages = await use_case.get_messages(str(session.id))

        # Assert
        assert len(messages) >= 2

    @pytest.mark.asyncio
    async def test_ownership_check(self, db_session):
        """Test: Session ownership validation."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = SessionUseCase(db_session)
        session = await use_case.create_session(
            user_id=str(user.id),
            title="Ownership Test",
        )

        owner = SessionOwner(user_id=user.id)

        # Act
        found = await use_case.get_session_with_ownership_check(
            str(session.id),
            owner,
        )

        # Assert
        assert found.id == session.id
