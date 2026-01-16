"""
Crypto Utilities 单元测试
"""

import uuid

import pytest

from utils.crypto import (
    decode_base64,
    encode_base64,
    generate_id,
    generate_secret,
    generate_short_id,
    hash_string,
)


@pytest.mark.unit
class TestCrypto:
    """加密工具测试"""

    def test_generate_id(self):
        """测试: 生成唯一 ID"""
        # Act
        id1 = generate_id()
        id2 = generate_id()

        # Assert
        assert id1 != id2
        assert isinstance(id1, str)
        assert len(id1) > 0
        # 验证是有效的 UUID
        uuid.UUID(id1)
        uuid.UUID(id2)

    def test_generate_short_id(self):
        """测试: 生成短 ID"""
        # Act
        short_id = generate_short_id()

        # Assert
        assert isinstance(short_id, str)
        assert len(short_id) == 8

    def test_generate_short_id_custom_length(self):
        """测试: 生成自定义长度的短 ID"""
        # Arrange
        length = 12

        # Act
        short_id = generate_short_id(length)

        # Assert
        assert len(short_id) == length

    def test_generate_secret(self):
        """测试: 生成密钥"""
        # Act
        secret = generate_secret()

        # Assert
        assert isinstance(secret, str)
        assert len(secret) == 64  # 32 bytes * 2 (hex)

    def test_generate_secret_custom_length(self):
        """测试: 生成自定义长度的密钥"""
        # Arrange
        length = 16

        # Act
        secret = generate_secret(length)

        # Assert
        assert len(secret) == length * 2  # hex encoding

    def test_hash_string_sha256(self):
        """测试: SHA256 哈希字符串"""
        # Arrange
        text = "test_string"

        # Act
        hash_value = hash_string(text, algorithm="sha256")

        # Assert
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA256 输出 32 bytes = 64 hex chars
        # 相同输入应该产生相同输出
        assert hash_string(text, algorithm="sha256") == hash_value

    def test_hash_string_md5(self):
        """测试: MD5 哈希字符串"""
        # Arrange
        text = "test_string"

        # Act
        hash_value = hash_string(text, algorithm="md5")

        # Assert
        assert isinstance(hash_value, str)
        assert len(hash_value) == 32  # MD5 输出 16 bytes = 32 hex chars

    def test_hash_string_different_inputs(self):
        """测试: 不同输入产生不同哈希"""
        # Arrange
        text1 = "test_string_1"
        text2 = "test_string_2"

        # Act
        hash1 = hash_string(text1)
        hash2 = hash_string(text2)

        # Assert
        assert hash1 != hash2

    def test_hash_string_unicode(self):
        """测试: Unicode 字符串哈希"""
        # Arrange
        text = "测试字符串"

        # Act
        hash_value = hash_string(text)

        # Assert
        assert isinstance(hash_value, str)
        assert len(hash_value) > 0

    def test_encode_base64(self):
        """测试: Base64 编码"""
        # Arrange
        data = b"Hello, World!"

        # Act
        encoded = encode_base64(data)

        # Assert
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_decode_base64(self):
        """测试: Base64 解码"""
        # Arrange
        original_data = b"Hello, World!"
        encoded = encode_base64(original_data)

        # Act
        decoded = decode_base64(encoded)

        # Assert
        assert decoded == original_data

    def test_encode_decode_roundtrip(self):
        """测试: Base64 编码解码往返"""
        # Arrange
        original_data = b"Test data for encoding and decoding"

        # Act
        encoded = encode_base64(original_data)
        decoded = decode_base64(encoded)

        # Assert
        assert decoded == original_data

    def test_encode_base64_empty(self):
        """测试: Base64 编码空数据"""
        # Arrange
        data = b""

        # Act
        encoded = encode_base64(data)

        # Assert
        assert encoded == ""

    def test_decode_base64_empty(self):
        """测试: Base64 解码空字符串"""
        # Arrange
        encoded = ""

        # Act
        decoded = decode_base64(encoded)

        # Assert
        assert decoded == b""
