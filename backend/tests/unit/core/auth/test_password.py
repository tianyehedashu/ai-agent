"""
Password Management 单元测试
"""

import pytest

from core.auth.password import hash_password, verify_password


@pytest.mark.unit
class TestPassword:
    """密码管理测试"""

    def test_hash_password(self):
        """测试: 哈希密码"""
        # Arrange
        password = "test_password_123"

        # Act
        hashed = hash_password(password)

        # Assert
        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")  # bcrypt 哈希格式

    def test_hash_password_different_salts(self):
        """测试: 相同密码生成不同的哈希（因为盐不同）"""
        # Arrange
        password = "same_password"

        # Act
        hashed1 = hash_password(password)
        hashed2 = hash_password(password)

        # Assert
        assert hashed1 != hashed2  # 每次哈希都不同

    def test_verify_password_correct(self):
        """测试: 验证正确密码"""
        # Arrange
        password = "test_password"
        hashed = hash_password(password)

        # Act
        result = verify_password(password, hashed)

        # Assert
        assert result is True

    def test_verify_password_incorrect(self):
        """测试: 验证错误密码"""
        # Arrange
        password = "test_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        # Act
        result = verify_password(wrong_password, hashed)

        # Assert
        assert result is False

    def test_verify_password_invalid_hash(self):
        """测试: 验证无效哈希"""
        # Arrange
        password = "test_password"
        invalid_hash = "invalid_hash_string"

        # Act
        result = verify_password(password, invalid_hash)

        # Assert
        assert result is False

    def test_verify_password_empty_strings(self):
        """测试: 验证空字符串"""
        # Arrange
        password = ""
        hashed = hash_password(password)

        # Act
        result = verify_password(password, hashed)

        # Assert
        assert result is True

    def test_hash_password_special_characters(self):
        """测试: 哈希包含特殊字符的密码"""
        # Arrange
        password = "p@ssw0rd!#$%^&*()"

        # Act
        hashed = hash_password(password)
        result = verify_password(password, hashed)

        # Assert
        assert result is True

    def test_hash_password_unicode(self):
        """测试: 哈希包含 Unicode 字符的密码"""
        # Arrange
        password = "密码123"

        # Act
        hashed = hash_password(password)
        result = verify_password(password, hashed)

        # Assert
        assert result is True
