"""
Session Ownership permission check unit tests.

Tests the behavior of check_session_ownership function.
"""

import uuid

import pytest

from domains.agent.infrastructure.models.session import Session
from domains.identity.presentation.deps import check_session_ownership
from domains.identity.presentation.schemas import CurrentUser
from exceptions import PermissionDeniedError


@pytest.mark.unit
class TestSessionOwnership:
    """Session ownership check tests."""

    def _create_mock_session(
        self, user_id: str | None = None, anonymous_user_id: str | None = None
    ) -> Session:
        """Create mock session object."""
        session = Session(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id) if user_id else None,
            anonymous_user_id=anonymous_user_id,
            status="active",
            message_count=0,
            token_count=0,
        )
        return session

    def _create_registered_user(self, user_id: str | None = None) -> CurrentUser:
        """Create registered user."""
        if user_id is None:
            user_id = str(uuid.uuid4())
        return CurrentUser(
            id=user_id,
            email=f"test_{user_id}@example.com",
            name="Test User",
            is_anonymous=False,
        )

    def _create_anonymous_user(self, anonymous_id: str | None = None) -> CurrentUser:
        """Create anonymous user."""
        if anonymous_id is None:
            anonymous_id = str(uuid.uuid4())
        from domains.identity.domain.types import Principal

        principal_id = Principal.make_anonymous_id(anonymous_id)
        return CurrentUser(
            id=principal_id,
            email=Principal.make_anonymous_email(anonymous_id),
            name="Anonymous User",
            is_anonymous=True,
        )

    def test_registered_user_owns_session(self):
        """Test: Registered user owns their own session."""
        # Arrange
        user_id = str(uuid.uuid4())
        user = self._create_registered_user(user_id)
        session = self._create_mock_session(user_id=user_id)

        # Act & Assert - should not raise exception
        check_session_ownership(session, user)

    def test_registered_user_cannot_access_other_user_session(self):
        """Test: Registered user cannot access other user's session."""
        # Arrange
        user1_id = str(uuid.uuid4())
        user2_id = str(uuid.uuid4())
        user1 = self._create_registered_user(user1_id)
        session = self._create_mock_session(user_id=user2_id)

        # Act & Assert
        with pytest.raises(PermissionDeniedError) as exc_info:
            check_session_ownership(session, user1)
        assert "permission" in exc_info.value.message.lower()

    def test_anonymous_user_owns_session(self):
        """Test: Anonymous user owns their own session."""
        # Arrange
        anonymous_id = str(uuid.uuid4())
        user = self._create_anonymous_user(anonymous_id)
        session = self._create_mock_session(anonymous_user_id=anonymous_id)

        # Act & Assert - should not raise exception
        check_session_ownership(session, user)

    def test_anonymous_user_cannot_access_other_anonymous_user_session(self):
        """Test: Anonymous user cannot access other anonymous user's session."""
        # Arrange
        anonymous_id_1 = str(uuid.uuid4())
        anonymous_id_2 = str(uuid.uuid4())
        user1 = self._create_anonymous_user(anonymous_id_1)
        session = self._create_mock_session(anonymous_user_id=anonymous_id_2)

        # Act & Assert
        with pytest.raises(PermissionDeniedError) as exc_info:
            check_session_ownership(session, user1)
        assert "permission" in exc_info.value.message.lower()

    def test_anonymous_user_cannot_access_registered_user_session(self):
        """Test: Anonymous user cannot access registered user's session."""
        # Arrange
        anonymous_id = str(uuid.uuid4())
        registered_user_id = str(uuid.uuid4())
        anonymous_user = self._create_anonymous_user(anonymous_id)
        session = self._create_mock_session(user_id=registered_user_id)

        # Act & Assert
        with pytest.raises(PermissionDeniedError) as exc_info:
            check_session_ownership(session, anonymous_user)
        assert "permission" in exc_info.value.message.lower()

    def test_registered_user_cannot_access_anonymous_user_session(self):
        """Test: Registered user cannot access anonymous user's session."""
        # Arrange
        registered_user_id = str(uuid.uuid4())
        anonymous_id = str(uuid.uuid4())
        registered_user = self._create_registered_user(registered_user_id)
        session = self._create_mock_session(anonymous_user_id=anonymous_id)

        # Act & Assert
        with pytest.raises(PermissionDeniedError) as exc_info:
            check_session_ownership(session, registered_user)
        assert "permission" in exc_info.value.message.lower()

    def test_registered_user_with_none_session_user_id(self):
        """Test: Registered user accessing session with user_id=None (anonymous session)."""
        # Arrange
        user_id = str(uuid.uuid4())
        user = self._create_registered_user(user_id)
        session = self._create_mock_session(user_id=None, anonymous_user_id="some-id")

        # Act & Assert
        with pytest.raises(PermissionDeniedError):
            check_session_ownership(session, user)

    def test_anonymous_user_with_none_session_anonymous_id(self):
        """Test: Anonymous user accessing session with anonymous_user_id=None (registered user session)."""
        # Arrange
        anonymous_id = str(uuid.uuid4())
        user = self._create_anonymous_user(anonymous_id)
        session = self._create_mock_session(user_id=str(uuid.uuid4()), anonymous_user_id=None)

        # Act & Assert
        with pytest.raises(PermissionDeniedError):
            check_session_ownership(session, user)
