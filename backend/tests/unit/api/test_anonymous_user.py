"""
匿名用户隔离单元测试

测试基于 Cookie 的匿名用户隔离机制
"""

import uuid

import pytest

from domains.identity.application import ANONYMOUS_USER_COOKIE
from domains.identity.application.principal_service import _get_or_create_anonymous_principal
from shared.kernel.types import Principal


@pytest.mark.unit
class TestAnonymousUserIsolation:
    """匿名用户隔离测试"""

    @pytest.mark.asyncio
    async def test_create_anonymous_principal(self, db_session):
        """测试: 为 anonymous_id 创建 Principal"""
        # Arrange
        anonymous_id = str(uuid.uuid4())

        # Act
        principal = await _get_or_create_anonymous_principal(db_session, anonymous_id)

        # Assert
        assert principal is not None
        assert principal.is_anonymous is True
        assert anonymous_id[:8] in principal.name
        assert Principal.make_anonymous_email(anonymous_id) == principal.email

    @pytest.mark.asyncio
    async def test_same_anonymous_id_returns_same_principal(self, db_session):
        """测试: 相同的 anonymous_id 返回相同的 Principal"""
        # Arrange
        anonymous_id = str(uuid.uuid4())

        # Act
        principal1 = await _get_or_create_anonymous_principal(db_session, anonymous_id)
        principal2 = await _get_or_create_anonymous_principal(db_session, anonymous_id)

        # Assert
        assert principal1 is not None
        assert principal2 is not None
        assert principal1.id == principal2.id
        assert principal1.email == principal2.email

    @pytest.mark.asyncio
    async def test_different_anonymous_ids_create_different_principals(self, db_session):
        """测试: 不同的 anonymous_id 创建不同的 Principal"""
        # Arrange
        anonymous_id_1 = str(uuid.uuid4())
        anonymous_id_2 = str(uuid.uuid4())

        # Act
        principal1 = await _get_or_create_anonymous_principal(db_session, anonymous_id_1)
        principal2 = await _get_or_create_anonymous_principal(db_session, anonymous_id_2)

        # Assert
        assert principal1 is not None
        assert principal2 is not None
        assert principal1.id != principal2.id
        assert principal1.email != principal2.email

    @pytest.mark.asyncio
    async def test_anonymous_principal_email_format(self, db_session):
        """测试: 匿名 Principal 邮箱格式正确"""
        # Arrange
        anonymous_id = "test-uuid-1234-5678"

        # Act
        principal = await _get_or_create_anonymous_principal(db_session, anonymous_id)

        # Assert
        assert principal is not None
        assert principal.email == Principal.make_anonymous_email(anonymous_id)

    @pytest.mark.asyncio
    async def test_anonymous_principal_name_format(self, db_session):
        """测试: 匿名 Principal 名称格式正确（包含 ID 前 8 位）"""
        # Arrange
        anonymous_id = "abcd1234-5678-9012"

        # Act
        principal = await _get_or_create_anonymous_principal(db_session, anonymous_id)

        # Assert
        assert principal is not None
        assert "abcd1234" in principal.name


@pytest.mark.unit
class TestAnonymousUserCookieConstant:
    """匿名用户 Cookie 常量测试"""

    def test_cookie_name_defined(self):
        """测试: Cookie 名称已定义"""
        assert ANONYMOUS_USER_COOKIE == "anonymous_user_id"
