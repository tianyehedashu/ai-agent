"""
匿名用户隔离单元测试

测试基于 Cookie 的匿名用户隔离机制
"""

import uuid

import pytest

from api.deps import ANONYMOUS_USER_COOKIE, _get_or_create_anonymous_user


@pytest.mark.unit
class TestAnonymousUserIsolation:
    """匿名用户隔离测试"""

    @pytest.mark.asyncio
    async def test_create_new_anonymous_user(self, db_session):
        """测试: 为新的 anonymous_id 创建新用户"""
        # Arrange
        anonymous_id = str(uuid.uuid4())

        # Act
        user = await _get_or_create_anonymous_user(db_session, anonymous_id)

        # Assert
        assert user is not None
        assert user.is_anonymous is True
        assert anonymous_id[:8] in user.name
        assert f"anonymous-{anonymous_id}@local" == user.email

    @pytest.mark.asyncio
    async def test_get_existing_anonymous_user(self, db_session):
        """测试: 使用相同的 anonymous_id 获取已存在的用户"""
        # Arrange
        anonymous_id = str(uuid.uuid4())

        # 先创建用户
        user1 = await _get_or_create_anonymous_user(db_session, anonymous_id)
        await db_session.commit()

        # Act - 再次调用相同的 anonymous_id
        user2 = await _get_or_create_anonymous_user(db_session, anonymous_id)

        # Assert
        assert user1 is not None
        assert user2 is not None
        assert user1.id == user2.id
        assert user1.email == user2.email

    @pytest.mark.asyncio
    async def test_different_anonymous_ids_create_different_users(self, db_session):
        """测试: 不同的 anonymous_id 创建不同的用户"""
        # Arrange
        anonymous_id_1 = str(uuid.uuid4())
        anonymous_id_2 = str(uuid.uuid4())

        # Act
        user1 = await _get_or_create_anonymous_user(db_session, anonymous_id_1)
        await db_session.commit()
        user2 = await _get_or_create_anonymous_user(db_session, anonymous_id_2)

        # Assert
        assert user1 is not None
        assert user2 is not None
        assert user1.id != user2.id
        assert user1.email != user2.email

    @pytest.mark.asyncio
    async def test_anonymous_user_email_format(self, db_session):
        """测试: 匿名用户邮箱格式正确"""
        # Arrange
        anonymous_id = "test-uuid-1234-5678"

        # Act
        user = await _get_or_create_anonymous_user(db_session, anonymous_id)

        # Assert
        assert user is not None
        assert user.email == f"anonymous-{anonymous_id}@local"

    @pytest.mark.asyncio
    async def test_anonymous_user_name_format(self, db_session):
        """测试: 匿名用户名称格式正确（包含 ID 前 8 位）"""
        # Arrange
        anonymous_id = "abcd1234-5678-9012"

        # Act
        user = await _get_or_create_anonymous_user(db_session, anonymous_id)

        # Assert
        assert user is not None
        assert "abcd1234" in user.name


@pytest.mark.unit
class TestAnonymousUserCookieConstant:
    """匿名用户 Cookie 常量测试"""

    def test_cookie_name_defined(self):
        """测试: Cookie 名称已定义"""
        assert ANONYMOUS_USER_COOKIE == "anonymous_user_id"
