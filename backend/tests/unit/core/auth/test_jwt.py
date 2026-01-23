"""
JWT Token Management 单元测试
"""

from datetime import UTC, datetime, timedelta

import pytest

from domains.identity.infrastructure.auth.jwt import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    verify_token,
)


@pytest.mark.unit
class TestJWT:
    """JWT 令牌管理测试"""

    def test_create_access_token(self):
        """测试: 创建访问令牌"""
        # Arrange
        user_id = "user_123"

        # Act
        token = create_access_token(user_id)

        # Assert
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_expires_delta(self):
        """测试: 创建带自定义过期时间的访问令牌"""
        # Arrange
        user_id = "user_123"
        expires_delta = timedelta(hours=2)

        # Act
        token = create_access_token(user_id, expires_delta=expires_delta)

        # Assert
        assert token is not None
        payload = verify_token(token, token_type="access")
        assert payload is not None
        assert payload.sub == user_id

    def test_create_access_token_with_extra_claims(self):
        """测试: 创建带额外声明的访问令牌"""
        # Arrange
        user_id = "user_123"
        extra_claims = {"role": "admin", "permissions": ["read", "write"]}

        # Act
        token = create_access_token(user_id, extra_claims=extra_claims)

        # Assert
        assert token is not None
        payload = verify_token(token, token_type="access")
        assert payload is not None

    def test_create_refresh_token(self):
        """测试: 创建刷新令牌"""
        # Arrange
        user_id = "user_123"

        # Act
        token = create_refresh_token(user_id)

        # Assert
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_access(self):
        """测试: 验证访问令牌"""
        # Arrange
        user_id = "user_123"
        token = create_access_token(user_id)

        # Act
        payload = verify_token(token, token_type="access")

        # Assert
        assert payload is not None
        assert payload.sub == user_id
        assert payload.type == "access"
        # payload.exp 现在已经是 UTC-aware datetime（代码已修复）
        assert payload.exp > datetime.now(UTC)

    def test_verify_token_refresh(self):
        """测试: 验证刷新令牌"""
        # Arrange
        user_id = "user_123"
        token = create_refresh_token(user_id)

        # Act
        payload = verify_token(token, token_type="refresh")

        # Assert
        assert payload is not None
        assert payload.sub == user_id
        assert payload.type == "refresh"

    def test_verify_token_wrong_type(self):
        """测试: 验证错误类型的令牌"""
        # Arrange
        user_id = "user_123"
        access_token = create_access_token(user_id)

        # Act
        payload = verify_token(access_token, token_type="refresh")

        # Assert
        assert payload is None  # 类型不匹配应返回 None

    def test_verify_token_invalid(self):
        """测试: 验证无效令牌"""
        # Arrange
        invalid_token = "invalid.token.here"

        # Act
        payload = verify_token(invalid_token)

        # Assert
        assert payload is None

    def test_verify_token_expired(self):
        """测试: 验证过期令牌"""
        # Arrange
        user_id = "user_123"
        # 创建已过期的令牌
        token = create_access_token(
            user_id,
            expires_delta=timedelta(seconds=-1),  # 已过期
        )

        # Act
        payload = verify_token(token)

        # Assert
        assert payload is None  # 过期令牌应返回 None

    def test_token_payload_model(self):
        """测试: TokenPayload 模型"""
        # Arrange
        now = datetime.now(UTC)
        expire = now + timedelta(hours=1)

        # Act
        payload = TokenPayload(
            sub="user_123",
            exp=expire,
            type="access",
            iat=now,
        )

        # Assert
        assert payload.sub == "user_123"
        assert payload.type == "access"
        assert payload.exp == expire
        assert payload.iat == now

    def test_create_token_different_users(self):
        """测试: 为不同用户创建令牌"""
        # Arrange
        user1_id = "user_1"
        user2_id = "user_2"

        # Act
        token1 = create_access_token(user1_id)
        token2 = create_access_token(user2_id)

        # Assert
        assert token1 != token2
        payload1 = verify_token(token1)
        payload2 = verify_token(token2)
        assert payload1.sub == user1_id
        assert payload2.sub == user2_id
