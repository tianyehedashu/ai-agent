"""
libs/crypto Fernet 加密工具单元测试

覆盖：
- derive_encryption_key 密钥派生
- encrypt_value / decrypt_value 对称加密解密
- mask_api_key 脱敏
- 错误密钥解密失败
"""

from cryptography.fernet import InvalidToken
import pytest

from libs.crypto import decrypt_value, derive_encryption_key, encrypt_value, mask_api_key


@pytest.mark.unit
class TestDeriveEncryptionKey:
    def test_deterministic(self):
        """相同密钥始终生成相同加密密钥"""
        key1 = derive_encryption_key("my-secret")
        key2 = derive_encryption_key("my-secret")
        assert key1 == key2

    def test_different_secrets_produce_different_keys(self):
        """不同密钥生成不同加密密钥"""
        key1 = derive_encryption_key("secret-a")
        key2 = derive_encryption_key("secret-b")
        assert key1 != key2

    def test_returns_base64_string(self):
        """返回 base64 编码字符串"""
        key = derive_encryption_key("test")
        assert isinstance(key, str)
        assert len(key) == 44  # 32 bytes -> base64 = 44 chars


@pytest.mark.unit
class TestEncryptDecrypt:
    @pytest.fixture()
    def enc_key(self) -> str:
        return derive_encryption_key("test-secret-key")

    def test_roundtrip(self, enc_key: str):
        """加密后解密得到原文"""
        plain = "sk-abc123xyz789"
        encrypted = encrypt_value(plain, enc_key)
        assert encrypted != plain
        decrypted = decrypt_value(encrypted, enc_key)
        assert decrypted == plain

    def test_different_plaintexts_produce_different_ciphertexts(self, enc_key: str):
        """不同明文产生不同密文"""
        c1 = encrypt_value("key-aaa", enc_key)
        c2 = encrypt_value("key-bbb", enc_key)
        assert c1 != c2

    def test_same_plaintext_produces_different_ciphertexts(self, enc_key: str):
        """Fernet 每次加密含随机 IV，相同明文密文不同"""
        c1 = encrypt_value("same-key", enc_key)
        c2 = encrypt_value("same-key", enc_key)
        assert c1 != c2
        assert decrypt_value(c1, enc_key) == decrypt_value(c2, enc_key)

    def test_wrong_key_raises(self, enc_key: str):
        """错误密钥解密抛 InvalidToken"""
        encrypted = encrypt_value("my-api-key", enc_key)
        wrong_key = derive_encryption_key("wrong-secret")
        with pytest.raises(InvalidToken):
            decrypt_value(encrypted, wrong_key)

    def test_unicode_plaintext(self, enc_key: str):
        """支持中文等 Unicode 字符"""
        plain = "密钥-测试-🔑"
        encrypted = encrypt_value(plain, enc_key)
        assert decrypt_value(encrypted, enc_key) == plain

    def test_empty_string(self, enc_key: str):
        """空字符串加解密"""
        encrypted = encrypt_value("", enc_key)
        assert decrypt_value(encrypted, enc_key) == ""


@pytest.mark.unit
class TestMaskApiKey:
    def test_normal_key(self):
        """正常长度 Key 脱敏"""
        assert mask_api_key("sk-abc123456xyz") == "sk-****6xyz"

    def test_short_key_returns_stars(self):
        """过短 Key 全部脱敏"""
        assert mask_api_key("short") == "****"
        assert mask_api_key("1234567") == "****"

    def test_exact_boundary(self):
        """长度恰好等于 prefix + suffix 时全部脱敏"""
        assert mask_api_key("abcdefg") == "****"  # 7 == 3 + 4

    def test_custom_visible_lengths(self):
        """自定义可见长度"""
        result = mask_api_key("sk-abcdefghijklmnop", visible_prefix=5, visible_suffix=3)
        assert result == "sk-ab****nop"

    def test_long_key(self):
        """长 Key 只显示首尾"""
        key = "sk-" + "x" * 100
        result = mask_api_key(key)
        assert result.startswith("sk-")
        assert result.endswith("x" * 4)
        assert "****" in result
