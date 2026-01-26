"""
Permission Context 单元测试

测试权限上下文的设置、获取和属性。
"""

import uuid

import pytest

from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    get_permission_context,
    set_permission_context,
)


@pytest.mark.unit
class TestPermissionContext:
    """权限上下文测试"""

    def test_create_registered_user_context(self):
        """测试: 创建注册用户权限上下文"""
        user_id = uuid.uuid4()
        ctx = PermissionContext(user_id=user_id, role="user")

        assert ctx.user_id == user_id
        assert ctx.anonymous_user_id is None
        assert ctx.role == "user"
        assert ctx.is_admin is False
        assert ctx.is_anonymous is False
        assert ctx.has_identity is True

    def test_create_anonymous_user_context(self):
        """测试: 创建匿名用户权限上下文"""
        anonymous_id = "test-anonymous-id"
        ctx = PermissionContext(anonymous_user_id=anonymous_id, role="user")

        assert ctx.user_id is None
        assert ctx.anonymous_user_id == anonymous_id
        assert ctx.role == "user"
        assert ctx.is_admin is False
        assert ctx.is_anonymous is True
        assert ctx.has_identity is True

    def test_create_admin_context(self):
        """测试: 创建管理员权限上下文"""
        user_id = uuid.uuid4()
        ctx = PermissionContext(user_id=user_id, role="admin")

        assert ctx.user_id == user_id
        assert ctx.role == "admin"
        assert ctx.is_admin is True
        assert ctx.is_anonymous is False

    def test_empty_context(self):
        """测试: 空权限上下文"""
        ctx = PermissionContext()

        assert ctx.user_id is None
        assert ctx.anonymous_user_id is None
        assert ctx.role == "user"
        assert ctx.is_admin is False
        assert ctx.is_anonymous is False
        assert ctx.has_identity is False

    def test_context_is_frozen(self):
        """测试: 权限上下文是不可变的"""
        from dataclasses import FrozenInstanceError

        ctx = PermissionContext(user_id=uuid.uuid4(), role="user")

        with pytest.raises(FrozenInstanceError):  # dataclass frozen 会抛出异常
            ctx.role = "admin"  # type: ignore[misc]


@pytest.mark.unit
class TestPermissionContextVar:
    """权限上下文 ContextVar 测试"""

    def test_set_and_get_context(self):
        """测试: 设置和获取权限上下文"""
        user_id = uuid.uuid4()
        ctx = PermissionContext(user_id=user_id, role="user")

        set_permission_context(ctx)
        retrieved = get_permission_context()

        assert retrieved is not None
        assert retrieved.user_id == user_id
        assert retrieved.role == "user"

    def test_get_context_when_not_set(self):
        """测试: 获取未设置的权限上下文"""
        # 确保上下文已清除
        clear_permission_context()
        ctx = get_permission_context()

        assert ctx is None

    def test_clear_context(self):
        """测试: 清除权限上下文"""
        ctx = PermissionContext(user_id=uuid.uuid4(), role="user")
        set_permission_context(ctx)

        # 验证已设置
        assert get_permission_context() is not None

        # 清除
        clear_permission_context()

        # 验证已清除
        assert get_permission_context() is None

    def test_set_none_context(self):
        """测试: 设置 None 上下文"""
        ctx = PermissionContext(user_id=uuid.uuid4(), role="user")
        set_permission_context(ctx)
        assert get_permission_context() is not None

        set_permission_context(None)
        assert get_permission_context() is None
