"""
User Service 单元测试
"""

import uuid

import pytest

from exceptions import AuthenticationError, NotFoundError
from services.user import UserService


@pytest.mark.unit
class TestUserService:
    """User Service 测试"""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        """测试: 创建用户"""
        # Arrange
        service = UserService(db_session)

        # Act
        user = await service.create(
            email="new@example.com",
            password="password123",
            name="New User",
        )

        # Assert
        assert user.email == "new@example.com"
        assert user.name == "New User"
        assert user.password_hash != "password123"  # 密码应该被哈希

    @pytest.mark.asyncio
    async def test_get_by_email(self, db_session):
        """测试: 通过邮箱获取用户"""
        # Arrange
        service = UserService(db_session)

        # 创建用户
        await service.create(
            email="find@example.com",
            password="password123",
            name="Find User",
        )

        # Act
        user = await service.get_by_email("find@example.com")
        not_found = await service.get_by_email("notfound@example.com")

        # Assert
        assert user is not None
        assert user.email == "find@example.com"
        assert not_found is None

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session):
        """测试: 通过 ID 获取用户"""
        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="id@example.com",
            password="password123",
            name="ID User",
        )

        # Act
        found = await service.get_by_id(str(user.id))
        not_found = await service.get_by_id(str(uuid.uuid4()))

        # Assert
        assert found is not None
        assert found.id == user.id
        assert not_found is None

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise(self, db_session):
        """测试: 通过 ID 获取用户，不存在则抛出异常"""
        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="raise@example.com",
            password="password123",
            name="Raise User",
        )

        # Act
        found = await service.get_by_id_or_raise(str(user.id))

        # Assert
        assert found.id == user.id

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.get_by_id_or_raise(str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_authenticate_success(self, db_session):
        """测试: 认证成功"""
        # Arrange
        service = UserService(db_session)
        await service.create(
            email="auth@example.com",
            password="correct_password",
            name="Auth User",
        )

        # Act
        user = await service.authenticate("auth@example.com", "correct_password")

        # Assert
        assert user.email == "auth@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, db_session):
        """测试: 认证失败"""
        # Arrange
        service = UserService(db_session)
        await service.create(
            email="authfail@example.com",
            password="correct_password",
            name="Auth Fail User",
        )

        # Act & Assert - 密码错误
        with pytest.raises(AuthenticationError):
            await service.authenticate("authfail@example.com", "wrong_password")

        # Act & Assert - 用户不存在
        with pytest.raises(AuthenticationError):
            await service.authenticate("notexist@example.com", "any_password")

    @pytest.mark.asyncio
    async def test_password_hashing(self, db_session):
        """测试: 密码哈希"""
        # Arrange
        service = UserService(db_session)
        password = "test_password_123"

        # Act
        hashed = service._hash_password(password)

        # Assert
        assert hashed != password
        assert service._verify_password(password, hashed)
        assert not service._verify_password("wrong_password", hashed)

    @pytest.mark.asyncio
    async def test_update_user(self, db_session):
        """测试: 更新用户信息"""
        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="update@example.com",
            password="password123",
            name="Original Name",
        )

        # Act
        updated = await service.update(
            str(user.id),
            name="Updated Name",
            avatar_url="https://example.com/avatar.jpg",
        )

        # Assert
        assert updated.name == "Updated Name"
        assert updated.avatar_url == "https://example.com/avatar.jpg"

    @pytest.mark.asyncio
    async def test_verify_password(self, db_session):
        """测试: 验证用户密码"""
        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="verify@example.com",
            password="correct_password",
            name="Verify User",
        )

        # Act
        correct = await service.verify_password(str(user.id), "correct_password")
        wrong = await service.verify_password(str(user.id), "wrong_password")
        not_exist = await service.verify_password(str(uuid.uuid4()), "any_password")

        # Assert
        assert correct is True
        assert wrong is False
        assert not_exist is False

    @pytest.mark.asyncio
    async def test_change_password(self, db_session):
        """测试: 修改密码"""
        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="changepwd@example.com",
            password="old_password",
            name="Change Pwd User",
        )

        # Act
        await service.change_password(
            str(user.id),
            old_password="old_password",
            new_password="new_password",
        )

        # Assert - 新密码可以验证
        assert await service.verify_password(str(user.id), "new_password") is True
        # 旧密码不能验证
        assert await service.verify_password(str(user.id), "old_password") is False

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, db_session):
        """测试: 修改密码时旧密码错误"""
        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="wrongold@example.com",
            password="old_password",
            name="Wrong Old User",
        )

        # Act & Assert
        with pytest.raises(AuthenticationError):
            await service.change_password(
                str(user.id),
                old_password="wrong_old_password",
                new_password="new_password",
            )

    @pytest.mark.asyncio
    async def test_create_token(self, db_session):
        """测试: 创建 Token"""
        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="token@example.com",
            password="password123",
            name="Token User",
        )

        # Act
        token_pair = await service.create_token(user)

        # Assert
        assert token_pair.access_token is not None
        assert len(token_pair.access_token) > 0
        assert token_pair.expires_in > 0

    @pytest.mark.asyncio
    async def test_get_user_from_token(self, db_session):
        """测试: 从 Token 获取用户"""
        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="fromtoken@example.com",
            password="password123",
            name="From Token User",
        )

        # Act
        token_pair = await service.create_token(user)
        retrieved_user = await service.get_user_from_token(token_pair.access_token)

        # Assert
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.email == user.email

    @pytest.mark.asyncio
    async def test_get_user_from_invalid_token(self, db_session):
        """测试: 无效 Token"""
        # Arrange
        service = UserService(db_session)

        # Act
        user = await service.get_user_from_token("invalid_token")

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_refresh_token(self, db_session):
        """测试: 刷新 Token"""
        import asyncio

        # Arrange
        service = UserService(db_session)
        user = await service.create(
            email="refresh@example.com",
            password="password123",
            name="Refresh User",
        )

        # 创建初始 token
        token_pair = await service.create_token(user)

        # 等待一秒，确保新的 token 有不同的时间戳
        await asyncio.sleep(1)

        # Act - 使用 refresh_token 而不是 access_token
        new_token_pair = await service.refresh_token(token_pair.refresh_token)

        # Assert
        assert new_token_pair.access_token is not None
        assert new_token_pair.refresh_token is not None
        # 新的 token 应该不同（因为创建时间不同）
        assert new_token_pair.access_token != token_pair.access_token
