"""
Title Use Case unit tests.
"""

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.identity.infrastructure.models.user import User
from domains.runtime.application.title_use_case import TitleUseCase


@pytest.mark.unit
class TestTitleUseCase:
    """Title Use Case tests."""

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
    async def test_generate_from_first_message(self, db_session):
        """Test: Generate title from first message."""
        # Arrange
        use_case = TitleUseCase(db_session)
        message = "How do I implement a binary search algorithm in Python?"

        # Mock LLM response
        with patch.object(
            use_case.llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value="Python二分查找",
        ):
            # Act
            title = await use_case.generate_from_first_message(message)

            # Assert
            assert title is not None
            assert len(title) > 0
            assert len(title) <= 50

    @pytest.mark.asyncio
    async def test_generate_from_first_message_long_title(self, db_session):
        """Test: Generate title truncation for long response."""
        # Arrange
        use_case = TitleUseCase(db_session)
        message = "Test message"
        long_title = "A" * 100  # Very long title

        # Mock LLM response
        with patch.object(
            use_case.llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value=long_title,
        ):
            # Act
            title = await use_case.generate_from_first_message(message)

            # Assert
            assert title is not None
            assert len(title) <= 50
            assert title.endswith("...")

    @pytest.mark.asyncio
    async def test_generate_from_first_message_error(self, db_session):
        """Test: Handle error during title generation."""
        # Arrange
        use_case = TitleUseCase(db_session)
        message = "Test message"

        # Mock LLM error
        with patch.object(
            use_case.llm_gateway,
            "chat",
            new_callable=AsyncMock,
            side_effect=Exception("LLM error"),
        ):
            # Act
            title = await use_case.generate_from_first_message(message)

            # Assert
            assert title is None

    @pytest.mark.asyncio
    async def test_update_title(self, db_session):
        """Test: Update session title."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = TitleUseCase(db_session)
        user_id = str(user.id)

        # Create session
        session = await use_case.session_use_case.create_session(
            user_id=user_id,
            title="Original Title",
        )

        # Act
        result = await use_case.update_title(
            session_id=str(session.id),
            title="Updated Title",
            user_id=user_id,
        )

        # Assert
        assert result is True
        updated_session = await use_case.session_use_case.get_session(str(session.id))
        assert updated_session.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_title_not_owner(self, db_session):
        """Test: Non-owner cannot update title."""
        # Arrange
        user = await self._create_test_user(db_session)
        other_user = await self._create_test_user(db_session)
        use_case = TitleUseCase(db_session)

        session = await use_case.session_use_case.create_session(
            user_id=str(user.id),
            title="Original Title",
        )

        # Act
        result = await use_case.update_title(
            session_id=str(session.id),
            title="Hacked Title",
            user_id=str(other_user.id),
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_update_title_session_not_found(self, db_session):
        """Test: Update title for non-existent session."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = TitleUseCase(db_session)

        # Act
        result = await use_case.update_title(
            session_id=str(uuid.uuid4()),
            title="Some Title",
            user_id=str(user.id),
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_update_title_truncation(self, db_session):
        """Test: Long title gets truncated."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = TitleUseCase(db_session)
        user_id = str(user.id)

        session = await use_case.session_use_case.create_session(
            user_id=user_id,
            title="Original",
        )

        long_title = "A" * 300

        # Act
        result = await use_case.update_title(
            session_id=str(session.id),
            title=long_title,
            user_id=user_id,
        )

        # Assert
        assert result is True
        updated_session = await use_case.session_use_case.get_session(str(session.id))
        assert len(updated_session.title) <= 200

    @pytest.mark.asyncio
    async def test_generate_and_update(self, db_session):
        """Test: Generate and update title."""
        # Arrange
        user = await self._create_test_user(db_session)
        use_case = TitleUseCase(db_session)
        user_id = str(user.id)

        session = await use_case.session_use_case.create_session(
            user_id=user_id,
            title=None,  # Default title
        )

        # Mock LLM response
        with patch.object(
            use_case.llm_gateway,
            "chat",
            new_callable=AsyncMock,
            return_value="AI生成的标题",
        ):
            # Act
            result = await use_case.generate_and_update(
                session_id=str(session.id),
                strategy="first_message",
                message="How does AI work?",
                user_id=user_id,
            )

            # Assert
            assert result is True
            updated_session = await use_case.session_use_case.get_session(
                str(session.id)
            )
            assert updated_session.title == "AI生成的标题"
