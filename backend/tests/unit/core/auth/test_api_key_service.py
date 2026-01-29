"""
API Key Domain Service 单元测试

测试 API Key 生成和验证功能
"""

from datetime import UTC, datetime, timedelta
import uuid

from cryptography.fernet import InvalidToken
import pytest

from domains.identity.domain.api_key_types import (
    API_KEY_SCOPE_GROUPS,
    ApiKeyEntity,
    ApiKeyFormat,
    ApiKeyScope,
    ApiKeyStatus,
)
from domains.identity.domain.services.api_key_service import (
    ApiKeyDomainService,
    ApiKeyGenerator,
)


@pytest.mark.unit
class TestApiKeyFormat:
    """API Key 格式常量测试"""

    def test_prefix_format(self):
        """测试: 前缀格式正确"""
        prefix = ApiKeyFormat.get_prefix()
        assert prefix == "sk_"

    def test_key_length(self):
        """测试: Key 长度符合预期"""
        # 格式: sk_16chars_32chars
        expected_length = (
            len("sk_") + ApiKeyFormat.KEY_ID_LENGTH + len("_") + ApiKeyFormat.SECRET_LENGTH
        )
        assert expected_length == ApiKeyFormat.FULL_KEY_LENGTH

    def test_mask_key_short(self):
        """测试: 掩码短 Key"""
        short_key = "sk_abc"
        masked = ApiKeyFormat.mask_key(short_key)
        assert masked == "***"

    def test_mask_key_normal(self):
        """测试: 掩码正常 Key"""
        key = "sk_1234567890123456_abcdefghijklmnop"
        masked = ApiKeyFormat.mask_key(key)
        assert masked == "sk_1234...mnop"


@pytest.mark.unit
class TestApiKeyGenerator:
    """API Key 生成器测试"""

    def test_generate_returns_tuple(self):
        """测试: 生成返回三元组"""
        generator = ApiKeyGenerator()
        plain_key, key_id, key_hash = generator.generate()

        assert isinstance(plain_key, str)
        assert isinstance(key_id, str)
        assert isinstance(key_hash, str)

    def test_generate_key_format(self):
        """测试: 生成的 Key 格式正确"""
        generator = ApiKeyGenerator()
        plain_key, _key_id, _key_hash = generator.generate()

        # 格式: sk_{key_id}_{secret}
        parts = plain_key.split("_")
        assert len(parts) == 3
        assert parts[0] == "sk"
        assert len(parts[1]) == ApiKeyFormat.KEY_ID_LENGTH

    def test_generate_key_id_length(self):
        """测试: key_id 长度正确"""
        generator = ApiKeyGenerator()
        _, key_id, _ = generator.generate()

        assert len(key_id) == ApiKeyFormat.KEY_ID_LENGTH

    def test_generate_unique_keys(self):
        """测试: 每次生成不同的 Key"""
        generator = ApiKeyGenerator()
        key1, _, _ = generator.generate()
        key2, _, _ = generator.generate()

        assert key1 != key2

    def test_hash_key_is_hash(self):
        """测试: 哈希后的 Key 与原文不同"""
        generator = ApiKeyGenerator()
        plain_key = "sk_test1234567890_testsecret1234567890"
        key_hash = generator.hash_key(plain_key)

        assert key_hash != plain_key
        # FastAPI Users 默认使用 argon2id 哈希
        assert key_hash.startswith("$argon2id$")

    def test_verify_key_correct(self):
        """测试: 验证正确的 Key"""
        generator = ApiKeyGenerator()
        plain_key, _, key_hash = generator.generate()

        result = generator.verify_key(plain_key, key_hash)

        assert result is True

    def test_verify_key_incorrect(self):
        """测试: 验证错误的 Key"""
        generator = ApiKeyGenerator()
        _plain_key, _, key_hash = generator.generate()

        result = generator.verify_key("wrong_key", key_hash)

        assert result is False

    def test_verify_key_different_hash(self):
        """测试: 用错误的哈希验证"""
        generator = ApiKeyGenerator()
        plain_key, _, _ = generator.generate()
        # 使用格式正确但内容错误的 argon2id 哈希
        wrong_hash = "$argon2id$v=19$m=4096,t=3,p=1$invalid$invalid"

        result = generator.verify_key(plain_key, wrong_hash)

        assert result is False


@pytest.mark.unit
class TestApiKeyDomainService:
    """API Key 领域服务测试"""

    def test_validate_creation_request_defaults(self):
        """测试: 使用默认值验证创建请求"""
        service = ApiKeyDomainService()

        expires_at, scopes = service.validate_creation_request(
            name="Test Key",
            description="Test description",
            scopes=None,  # 使用默认
            expires_in_days=90,
        )

        assert expires_at > datetime.now(UTC)
        assert scopes == API_KEY_SCOPE_GROUPS["read_only"]

    def test_validate_creation_request_custom_scopes(self):
        """测试: 使用自定义作用域"""
        service = ApiKeyDomainService()
        custom_scopes = {ApiKeyScope.AGENT_READ, ApiKeyScope.AGENT_EXECUTE}

        _expires_at, scopes = service.validate_creation_request(
            name="Test Key",
            description=None,
            scopes=custom_scopes,
            expires_in_days=30,
        )

        assert scopes == custom_scopes

    def test_validate_creation_request_max_expiry(self):
        """测试: 过期时间不能超过 1 年"""
        service = ApiKeyDomainService()

        with pytest.raises(ValueError, match="cannot exceed 1 year"):
            service.validate_creation_request(
                name="Test",
                description=None,
                scopes=None,
                expires_in_days=400,  # 超过 365 天
            )

    def test_validate_expiry_update(self):
        """测试: 验证过期时间更新"""
        service = ApiKeyDomainService()
        current = datetime.now(UTC) + timedelta(days=30)

        new_expiry = service.validate_expiry_update(current, 30)

        assert new_expiry == current + timedelta(days=30)

    def test_validate_expiry_update_exceeds_limit(self):
        """测试: 延长后总时间不能超过 1 年"""
        service = ApiKeyDomainService()
        current = datetime.now(UTC) + timedelta(days=300)

        with pytest.raises(ValueError, match="cannot exceed 1 year"):
            service.validate_expiry_update(current, 100)

    def test_is_valid_key_format_valid(self):
        """测试: 验证有效的 Key 格式"""
        service = ApiKeyDomainService()
        valid_key = "sk_1234567890123456_abcdefghijklmnopqrstuvwxyz"

        assert service.is_valid_key_format(valid_key) is True

    def test_is_valid_key_format_invalid_prefix(self):
        """测试: 无效前缀"""
        service = ApiKeyDomainService()

        assert service.is_valid_key_format("pk_1234_5678") is False

    def test_is_valid_key_format_invalid_parts(self):
        """测试: 部分数量不对"""
        service = ApiKeyDomainService()

        assert service.is_valid_key_format("sk_only_one_part") is False

    def test_is_valid_key_format_invalid_length(self):
        """测试: key_id 长度不对"""
        service = ApiKeyDomainService()

        assert service.is_valid_key_format("sk_too_short_secret") is False


@pytest.mark.unit
class TestApiKeyEntity:
    """API Key 实体测试"""

    def test_status_active(self):
        """测试: 激活状态"""
        entity = ApiKeyEntity(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            key_hash="hash",
            key_id="id123456789012",
            key_prefix="sk_",
            name="Test Key",
            description=None,
            scopes={ApiKeyScope.AGENT_READ},
            expires_at=datetime.now(UTC) + timedelta(days=30),
            is_active=True,
            last_used_at=None,
            usage_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert entity.status == ApiKeyStatus.ACTIVE
        assert entity.is_valid is True

    def test_status_expired(self):
        """测试: 过期状态"""
        entity = ApiKeyEntity(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            key_hash="hash",
            key_id="id123456789012",
            key_prefix="sk_",
            name="Test Key",
            description=None,
            scopes={ApiKeyScope.AGENT_READ},
            expires_at=datetime.now(UTC) - timedelta(days=1),  # 已过期
            is_active=True,
            last_used_at=None,
            usage_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert entity.status == ApiKeyStatus.EXPIRED
        assert entity.is_expired is True
        assert entity.is_valid is False

    def test_status_revoked(self):
        """测试: 撤销状态"""
        entity = ApiKeyEntity(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            key_hash="hash",
            key_id="id123456789012",
            key_prefix="sk_",
            name="Test Key",
            description=None,
            scopes={ApiKeyScope.AGENT_READ},
            expires_at=datetime.now(UTC) + timedelta(days=30),
            is_active=False,  # 已撤销
            last_used_at=None,
            usage_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert entity.status == ApiKeyStatus.REVOKED
        assert entity.is_valid is False

    def test_can_access(self):
        """测试: 权限检查"""
        entity = ApiKeyEntity(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            key_hash="hash",
            key_id="id123456789012",
            key_prefix="sk_",
            name="Test Key",
            description=None,
            scopes={ApiKeyScope.AGENT_READ, ApiKeyScope.AGENT_EXECUTE},
            expires_at=datetime.now(UTC) + timedelta(days=30),
            is_active=True,
            last_used_at=None,
            usage_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert entity.can_access(ApiKeyScope.AGENT_READ) is True
        assert entity.can_access(ApiKeyScope.SESSION_READ) is False

    def test_can_access_revoked(self):
        """测试: 撤销的 Key 无权限"""
        entity = ApiKeyEntity(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            key_hash="hash",
            key_id="id123456789012",
            key_prefix="sk_",
            name="Test Key",
            description=None,
            scopes={ApiKeyScope.AGENT_READ},
            expires_at=datetime.now(UTC) + timedelta(days=30),
            is_active=False,  # 已撤销
            last_used_at=None,
            usage_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert entity.can_access(ApiKeyScope.AGENT_READ) is False

    def test_days_until_expiry(self):
        """测试: 距离过期天数"""
        expires_at = datetime.now(UTC) + timedelta(days=7)
        entity = ApiKeyEntity(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            key_hash="hash",
            key_id="id123456789012",
            key_prefix="sk_",
            name="Test Key",
            description=None,
            scopes={ApiKeyScope.AGENT_READ},
            expires_at=expires_at,
            is_active=True,
            last_used_at=None,
            usage_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 允许 1 天的误差
        assert 6 <= entity.days_until_expiry <= 7


@pytest.mark.unit
class TestApiKeyEncryption:
    """API Key 加密/解密测试"""

    def test_derive_encryption_key(self):
        """测试: 从密钥派生加密密钥"""
        secret = "my-app-secret-key"
        encryption_key = ApiKeyGenerator.derive_encryption_key(secret)

        # 应该是有效的 base64 编码的 Fernet 密钥（44 字符）
        assert len(encryption_key) == 44

    def test_derive_encryption_key_deterministic(self):
        """测试: 相同的密钥派生出相同的加密密钥"""
        secret = "my-app-secret-key"
        key1 = ApiKeyGenerator.derive_encryption_key(secret)
        key2 = ApiKeyGenerator.derive_encryption_key(secret)

        assert key1 == key2

    def test_encrypt_decrypt_roundtrip(self):
        """测试: 加密后可以正确解密"""
        generator = ApiKeyGenerator()
        secret = "test-secret"
        encryption_key = generator.derive_encryption_key(secret)

        plain_key = "sk_1234567890123456_abcdefghijklmnopqrstuvwxyz123456"

        encrypted = generator.encrypt_key(plain_key, encryption_key)
        decrypted = generator.decrypt_key(encrypted, encryption_key)

        assert decrypted == plain_key

    def test_encrypt_different_keys(self):
        """测试: 相同的明文加密后结果不同（由于 IV）"""
        generator = ApiKeyGenerator()
        secret = "test-secret"
        encryption_key = generator.derive_encryption_key(secret)

        plain_key = "sk_1234567890123456_abcdefghijklmnopqrstuvwxyz123456"

        encrypted1 = generator.encrypt_key(plain_key, encryption_key)
        encrypted2 = generator.encrypt_key(plain_key, encryption_key)

        # Fernet 每次加密都会生成不同的结果（因为包含时间戳和随机 IV）
        assert encrypted1 != encrypted2

    def test_decrypt_with_wrong_key_fails(self):
        """测试: 使用错误的密钥解密失败"""
        generator = ApiKeyGenerator()

        key1 = generator.derive_encryption_key("secret-1")
        key2 = generator.derive_encryption_key("secret-2")

        plain_key = "sk_1234567890123456_abcdefghijklmnopqrstuvwxyz123456"

        encrypted = generator.encrypt_key(plain_key, key1)

        with pytest.raises(InvalidToken):
            generator.decrypt_key(encrypted, key2)

    def test_encrypt_with_instance_key(self):
        """测试: 使用初始化时传入的加密密钥"""
        secret = "test-secret"
        encryption_key = ApiKeyGenerator.derive_encryption_key(secret)
        generator = ApiKeyGenerator(encryption_key=encryption_key)

        plain_key = "sk_1234567890123456_abcdefghijklmnopqrstuvwxyz123456"

        encrypted = generator.encrypt_key(plain_key, encryption_key)
        decrypted = generator.decrypt_key(encrypted, encryption_key)

        assert decrypted == plain_key

    def test_encrypt_without_key_raises(self):
        """测试: 未提供加密密钥时抛出异常"""
        generator = ApiKeyGenerator()  # 未传入 encryption_key

        with pytest.raises(ValueError, match="encryption_key is required"):
            generator.encrypt_key("sk_test", None)  # 传入 None 应该触发我们的检查

    def test_decrypt_without_key_raises(self):
        """测试: 未提供加密密钥时抛出异常"""
        generator = ApiKeyGenerator()  # 未传入 encryption_key

        with pytest.raises(ValueError, match="encryption_key is required"):
            generator.decrypt_key("encrypted", None)  # 传入 None 应该触发我们的检查

