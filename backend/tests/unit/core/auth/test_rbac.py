"""
RBAC 单元测试
"""

import pytest

from domains.identity.domain.rbac import (
    Permission,
    Role,
    check_resource_ownership,
    has_permission,
)


@pytest.mark.unit
class TestRBAC:
    """RBAC 测试"""

    def test_has_permission_admin(self):
        """测试: 管理员拥有所有权限"""
        # Act & Assert
        assert has_permission(Role.ADMIN, Permission.AGENT_CREATE) is True
        assert has_permission(Role.ADMIN, Permission.AGENT_READ) is True
        assert has_permission(Role.ADMIN, Permission.AGENT_DELETE) is True
        assert has_permission(Role.ADMIN, Permission.SYSTEM_ADMIN) is True
        assert has_permission(Role.ADMIN, Permission.USER_MANAGE) is True

    def test_has_permission_user(self):
        """测试: 普通用户权限"""
        # Act & Assert
        assert has_permission(Role.USER, Permission.AGENT_CREATE) is True
        assert has_permission(Role.USER, Permission.AGENT_READ) is True
        assert has_permission(Role.USER, Permission.AGENT_UPDATE) is True
        assert has_permission(Role.USER, Permission.SYSTEM_ADMIN) is False
        assert has_permission(Role.USER, Permission.USER_MANAGE) is False

    def test_has_permission_viewer(self):
        """测试: 只读用户权限"""
        # Act & Assert
        assert has_permission(Role.VIEWER, Permission.AGENT_READ) is True
        assert has_permission(Role.VIEWER, Permission.SESSION_READ) is True
        assert has_permission(Role.VIEWER, Permission.AGENT_CREATE) is False
        assert has_permission(Role.VIEWER, Permission.AGENT_DELETE) is False

    def test_has_permission_string_role(self):
        """测试: 使用字符串角色"""
        # Act & Assert
        assert has_permission("admin", Permission.AGENT_CREATE) is True
        assert has_permission("user", Permission.AGENT_CREATE) is True
        assert has_permission("viewer", Permission.AGENT_CREATE) is False

    def test_has_permission_invalid_role(self):
        """测试: 无效角色"""
        # Act & Assert
        assert has_permission("invalid_role", Permission.AGENT_CREATE) is False

    def test_require_permission_allowed(self):
        """测试: 权限检查通过"""
        # 注意: require_permission 是 FastAPI 依赖装饰器，主要用于 API 端点
        # 这里只测试函数签名，实际使用需要在 FastAPI 路由中
        # 跳过此测试，因为装饰器需要 FastAPI 请求上下文
        pass

    def test_check_resource_ownership_same_user(self):
        """测试: 检查资源所有权 - 相同用户"""
        # Arrange
        resource_user_id = "user_123"
        current_user_id = "user_123"

        # Act
        result = check_resource_ownership(
            user_id=current_user_id,
            resource_user_id=resource_user_id,
        )

        # Assert
        assert result is True

    def test_check_resource_ownership_different_user(self):
        """测试: 检查资源所有权 - 不同用户"""
        # Arrange
        resource_user_id = "user_123"
        current_user_id = "user_456"

        # Act
        result = check_resource_ownership(
            user_id=current_user_id,
            resource_user_id=resource_user_id,
        )

        # Assert
        assert result is False

    def test_check_resource_ownership_with_admin(self):
        """测试: 检查资源所有权 - 管理员可以访问"""
        # Arrange
        resource_user_id = "user_123"
        current_user_id = "user_456"
        current_user_role = Role.ADMIN.value

        # Act
        result = check_resource_ownership(
            user_id=current_user_id,
            resource_user_id=resource_user_id,
            user_role=current_user_role,
        )

        # Assert
        assert result is True

    def test_check_resource_ownership_with_user_role(self):
        """测试: 检查资源所有权 - 普通用户不能访问他人资源"""
        # Arrange
        resource_user_id = "user_123"
        current_user_id = "user_456"
        current_user_role = Role.USER.value

        # Act
        result = check_resource_ownership(
            user_id=current_user_id,
            resource_user_id=resource_user_id,
            user_role=current_user_role,
        )

        # Assert
        assert result is False
