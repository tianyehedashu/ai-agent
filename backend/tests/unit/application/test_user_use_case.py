"""
User Use Case unit tests.
"""

import uuid

import pytest

from domains.identity.application.user_use_case import UserUseCase
from exceptions import AuthenticationError


@pytest.mark.unit
class TestUserUseCase:
    """User Use Case tests."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        """Test: Create user."""
        # Arrange
        use_case = UserUseCase(db_session)
        email = f"test_{uuid.uuid4()}@example.com"

        # Act
        user = await use_case.create_user(
            email=email,
            password="SecurePass123!",
            name="Test User",
        )

        # Assert
        assert user.id is not None
        assert user.email == email
        assert user.name == "Test User"
        assert user.hashed_password != "SecurePass123!"

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_session):
        """Test: Get user by ID."""
        # Arrange
        use_case = UserUseCase(db_session)
        user = await use_case.create_user(
            email=f"test_{uuid.uuid4()}@example.com",
            password="SecurePass123!",
            name="Test User",
        )

        # Act
        found = await use_case.get_user_by_id(str(user.id))

        # Assert
        assert found is not None
        assert found.id == user.id

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, db_session):
        """Test: Get non-existent user."""
        # Arrange
        use_case = UserUseCase(db_session)

        # Act
        found = await use_case.get_user_by_id(str(uuid.uuid4()))

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, db_session):
        """Test: Get user by email."""
        # Arrange
        use_case = UserUseCase(db_session)
        email = f"test_{uuid.uuid4()}@example.com"
        await use_case.create_user(
            email=email,
            password="SecurePass123!",
            name="Test User",
        )

        # Act
        found = await use_case.get_user_by_email(email)

        # Assert
        assert found is not None
        assert found.email == email

    @pytest.mark.asyncio
    async def test_authenticate_success(self, db_session):
        """Test: Successful authentication."""
        # Arrange
        use_case = UserUseCase(db_session)
        email = f"test_{uuid.uuid4()}@example.com"
        password = "SecurePass123!"
        await use_case.create_user(
            email=email,
            password=password,
            name="Test User",
        )

        # Act
        user = await use_case.authenticate(email, password)

        # Assert
        assert user is not None
        assert user.email == email

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, db_session):
        """Test: Authentication with wrong password."""
        # Arrange
        use_case = UserUseCase(db_session)
        email = f"test_{uuid.uuid4()}@example.com"
        await use_case.create_user(
            email=email,
            password="CorrectPassword",
            name="Test User",
        )

        # Act & Assert
        with pytest.raises(AuthenticationError):
            await use_case.authenticate(email, "WrongPassword")

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, db_session):
        """Test: Authentication with non-existent email."""
        # Arrange
        use_case = UserUseCase(db_session)

        # Act & Assert
        with pytest.raises(AuthenticationError):
            await use_case.authenticate("nonexistent@example.com", "password")

    @pytest.mark.asyncio
    async def test_update_user(self, db_session):
        """Test: Update user information."""
        # Arrange
        use_case = UserUseCase(db_session)
        user = await use_case.create_user(
            email=f"test_{uuid.uuid4()}@example.com",
            password="SecurePass123!",
            name="Original Name",
        )

        # Act
        updated = await use_case.update_user(
            user_id=str(user.id),
            name="Updated Name",
        )

        # Assert
        assert updated.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_verify_password_correct(self, db_session):
        """Test: Verify correct password."""
        # Arrange
        use_case = UserUseCase(db_session)
        password = "SecurePass123!"
        user = await use_case.create_user(
            email=f"test_{uuid.uuid4()}@example.com",
            password=password,
            name="Test User",
        )

        # Act
        result = await use_case.verify_password(str(user.id), password)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_wrong(self, db_session):
        """Test: Verify wrong password."""
        # Arrange
        use_case = UserUseCase(db_session)
        user = await use_case.create_user(
            email=f"test_{uuid.uuid4()}@example.com",
            password="CorrectPassword",
            name="Test User",
        )

        # Act
        result = await use_case.verify_password(str(user.id), "WrongPassword")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_change_password_success(self, db_session):
        """Test: Change password successfully."""
        # Arrange
        use_case = UserUseCase(db_session)
        old_password = "OldPassword123!"
        new_password = "NewPassword456!"
        user = await use_case.create_user(
            email=f"test_{uuid.uuid4()}@example.com",
            password=old_password,
            name="Test User",
        )

        # Act
        await use_case.change_password(str(user.id), old_password, new_password)

        # Assert
        result = await use_case.verify_password(str(user.id), new_password)
        assert result is True

    @pytest.mark.asyncio
    async def test_change_password_wrong_old_password(self, db_session):
        """Test: Change password with wrong old password."""
        # Arrange
        use_case = UserUseCase(db_session)
        user = await use_case.create_user(
            email=f"test_{uuid.uuid4()}@example.com",
            password="CorrectOldPassword",
            name="Test User",
        )

        # Act & Assert
        with pytest.raises(AuthenticationError):
            await use_case.change_password(
                str(user.id),
                "WrongOldPassword",
                "NewPassword",
            )
