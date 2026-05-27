"""
匿名用户隔离单元测试

测试基于 Cookie 的匿名用户隔离机制
"""

import uuid

import pytest
from sqlalchemy import func, select

from domains.identity.application import ANONYMOUS_USER_COOKIE
from domains.identity.application.principal_service import build_anonymous_principal
from domains.identity.domain.types import Principal
from domains.identity.infrastructure.models.user import User


@pytest.mark.unit
class TestAnonymousUserIsolation:
    """匿名用户隔离测试"""

    @pytest.mark.asyncio
    async def test_create_anonymous_principal_does_not_persist_user(self, db_session):
        """测试: 创建匿名 Principal 不写入 users 表"""
        anonymous_id = str(uuid.uuid4())
        before = await db_session.scalar(select(func.count()).select_from(User))

        build_anonymous_principal(anonymous_id)

        after = await db_session.scalar(select(func.count()).select_from(User))
        assert after == before

    def test_create_anonymous_principal(self):
        """测试: 为 anonymous_id 创建 Principal"""
        anonymous_id = str(uuid.uuid4())
        principal = build_anonymous_principal(anonymous_id)

        assert principal.is_anonymous is True
        assert anonymous_id[:8] in principal.name
        assert Principal.make_anonymous_email(anonymous_id) == principal.email

    def test_same_anonymous_id_returns_same_principal(self):
        """测试: 相同的 anonymous_id 返回相同的 Principal"""
        anonymous_id = str(uuid.uuid4())
        principal1 = build_anonymous_principal(anonymous_id)
        principal2 = build_anonymous_principal(anonymous_id)

        assert principal1.id == principal2.id
        assert principal1.email == principal2.email

    def test_different_anonymous_ids_create_different_principals(self):
        """测试: 不同的 anonymous_id 创建不同的 Principal"""
        principal1 = build_anonymous_principal(str(uuid.uuid4()))
        principal2 = build_anonymous_principal(str(uuid.uuid4()))

        assert principal1.id != principal2.id
        assert principal1.email != principal2.email

    def test_anonymous_principal_email_format(self):
        """测试: 匿名 Principal 邮箱格式正确"""
        anonymous_id = "test-uuid-1234-5678"
        principal = build_anonymous_principal(anonymous_id)
        assert principal.email == Principal.make_anonymous_email(anonymous_id)

    def test_anonymous_principal_name_format(self):
        """测试: 匿名 Principal 名称格式正确（包含 ID 前 8 位）"""
        anonymous_id = "abcd1234-5678-9012"
        principal = build_anonymous_principal(anonymous_id)
        assert "abcd1234" in principal.name


@pytest.mark.unit
class TestAnonymousUserCookieConstant:
    """匿名用户 Cookie 常量测试"""

    def test_cookie_name_defined(self):
        """测试: Cookie 名称已定义"""
        assert ANONYMOUS_USER_COOKIE == "anonymous_user_id"
