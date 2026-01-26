"""
权限检查函数单元测试

测试 check_ownership、check_ownership_or_public、check_session_ownership 等函数。
"""

import uuid

import pytest

from domains.agent.infrastructure.models.session import Session
from domains.identity.presentation.deps import (
    ADMIN_ROLE,
    check_ownership,
    check_ownership_or_public,
    check_session_ownership,
)
from domains.identity.presentation.schemas import CurrentUser
from exceptions import PermissionDeniedError


@pytest.mark.unit
class TestCheckOwnership:
    """check_ownership 测试"""

    def test_owner_can_access(self):
        """测试: 所有者可以访问资源"""
        user_id = str(uuid.uuid4())
        user = CurrentUser(
            id=user_id,
            email="test@example.com",
            name="Test User",
            is_anonymous=False,
            role="user",
        )

        # 不应该抛出异常
        check_ownership(user_id, user, "Resource")

    def test_non_owner_cannot_access(self):
        """测试: 非所有者不能访问资源"""
        user1_id = str(uuid.uuid4())
        user2_id = str(uuid.uuid4())
        user = CurrentUser(
            id=user1_id,
            email="test@example.com",
            name="Test User",
            is_anonymous=False,
            role="user",
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            check_ownership(user2_id, user, "Resource")
        assert "permission" in exc_info.value.message.lower()

    def test_admin_can_access_all(self):
        """测试: 管理员可以访问所有资源"""
        admin_id = str(uuid.uuid4())
        resource_owner_id = str(uuid.uuid4())
        admin = CurrentUser(
            id=admin_id,
            email="admin@example.com",
            name="Admin",
            is_anonymous=False,
            role=ADMIN_ROLE,
        )

        # 管理员应该可以访问，不抛出异常
        check_ownership(resource_owner_id, admin, "Resource")

    def test_custom_resource_name(self):
        """测试: 自定义资源名称"""
        user_id = str(uuid.uuid4())
        user = CurrentUser(
            id=user_id,
            email="test@example.com",
            name="Test User",
            is_anonymous=False,
            role="user",
        )

        with pytest.raises(PermissionDeniedError) as exc_info:
            check_ownership(str(uuid.uuid4()), user, "CustomResource")
        assert "customresource" in exc_info.value.message.lower()


@pytest.mark.unit
class TestCheckOwnershipOrPublic:
    """check_ownership_or_public 测试"""

    def test_owner_can_access_private(self):
        """测试: 所有者可以访问私有资源"""
        user_id = str(uuid.uuid4())
        user = CurrentUser(
            id=user_id,
            email="test@example.com",
            name="Test User",
            is_anonymous=False,
            role="user",
        )

        check_ownership_or_public(user_id, user, is_public=False, resource_name="Resource")

    def test_anyone_can_access_public(self):
        """测试: 任何人都可以访问公开资源"""
        user_id = str(uuid.uuid4())
        resource_owner_id = str(uuid.uuid4())
        user = CurrentUser(
            id=user_id,
            email="test@example.com",
            name="Test User",
            is_anonymous=False,
            role="user",
        )

        # 公开资源，非所有者也可以访问
        check_ownership_or_public(resource_owner_id, user, is_public=True, resource_name="Resource")

    def test_non_owner_cannot_access_private(self):
        """测试: 非所有者不能访问私有资源"""
        user1_id = str(uuid.uuid4())
        user2_id = str(uuid.uuid4())
        user = CurrentUser(
            id=user1_id,
            email="test@example.com",
            name="Test User",
            is_anonymous=False,
            role="user",
        )

        with pytest.raises(PermissionDeniedError):
            check_ownership_or_public(user2_id, user, is_public=False, resource_name="Resource")

    def test_admin_can_access_all(self):
        """测试: 管理员可以访问所有资源（包括私有）"""
        admin_id = str(uuid.uuid4())
        resource_owner_id = str(uuid.uuid4())
        admin = CurrentUser(
            id=admin_id,
            email="admin@example.com",
            name="Admin",
            is_anonymous=False,
            role=ADMIN_ROLE,
        )

        # 管理员应该可以访问，不抛出异常
        check_ownership_or_public(resource_owner_id, admin, is_public=False, resource_name="Resource")


@pytest.mark.unit
class TestCheckSessionOwnership:
    """check_session_ownership 测试"""

    def _create_session(
        self, user_id: uuid.UUID | None = None, anonymous_user_id: str | None = None
    ) -> Session:
        """创建测试会话"""
        return Session(
            id=uuid.uuid4(),
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            status="active",
            message_count=0,
            token_count=0,
        )

    def _create_registered_user(self, user_id: str | None = None) -> CurrentUser:
        """创建注册用户"""
        if user_id is None:
            user_id = str(uuid.uuid4())
        return CurrentUser(
            id=user_id,
            email="test@example.com",
            name="Test User",
            is_anonymous=False,
            role="user",
        )

    def _create_anonymous_user(self, anonymous_id: str | None = None) -> CurrentUser:
        """创建匿名用户"""
        if anonymous_id is None:
            anonymous_id = str(uuid.uuid4())
        from domains.identity.domain.types import Principal

        principal_id = Principal.make_anonymous_id(anonymous_id)
        return CurrentUser(
            id=principal_id,
            email=Principal.make_anonymous_email(anonymous_id),
            name="Anonymous",
            is_anonymous=True,
            role="user",
        )

    def test_registered_user_owns_session(self):
        """测试: 注册用户拥有自己的会话"""
        user_id = uuid.uuid4()
        user = self._create_registered_user(str(user_id))
        session = self._create_session(user_id=user_id)

        check_session_ownership(session, user)

    def test_registered_user_cannot_access_other_session(self):
        """测试: 注册用户不能访问其他用户的会话"""
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        user = self._create_registered_user(str(user1_id))
        session = self._create_session(user_id=user2_id)

        with pytest.raises(PermissionDeniedError):
            check_session_ownership(session, user)

    def test_anonymous_user_owns_session(self):
        """测试: 匿名用户拥有自己的会话"""
        anonymous_id = "test-anonymous-id"
        user = self._create_anonymous_user(anonymous_id)
        session = self._create_session(anonymous_user_id=anonymous_id)

        check_session_ownership(session, user)

    def test_anonymous_user_cannot_access_other_session(self):
        """测试: 匿名用户不能访问其他匿名用户的会话"""
        anonymous_id1 = "anon-1"
        anonymous_id2 = "anon-2"
        user = self._create_anonymous_user(anonymous_id1)
        session = self._create_session(anonymous_user_id=anonymous_id2)

        with pytest.raises(PermissionDeniedError):
            check_session_ownership(session, user)

    def test_admin_can_access_all_sessions(self):
        """测试: 管理员可以访问所有会话"""
        admin_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        admin = CurrentUser(
            id=str(admin_id),
            email="admin@example.com",
            name="Admin",
            is_anonymous=False,
            role=ADMIN_ROLE,
        )
        session = self._create_session(user_id=other_user_id)

        # 管理员应该可以访问，不抛出异常
        check_session_ownership(session, admin)

    def test_admin_can_access_anonymous_session(self):
        """测试: 管理员可以访问匿名用户的会话"""
        admin_id = uuid.uuid4()
        anonymous_id = "test-anonymous-id"
        admin = CurrentUser(
            id=str(admin_id),
            email="admin@example.com",
            name="Admin",
            is_anonymous=False,
            role=ADMIN_ROLE,
        )
        session = self._create_session(anonymous_user_id=anonymous_id)

        # 管理员应该可以访问，不抛出异常
        check_session_ownership(session, admin)
