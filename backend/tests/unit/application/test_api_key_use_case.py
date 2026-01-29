"""
API Key Use Case 单元测试

测试 API Key 业务逻辑
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.identity.application.api_key_use_case import ApiKeyUseCase
from domains.identity.domain.api_key_types import (
    ApiKeyCreateRequest,
    ApiKeyScope,
)
from domains.identity.domain.services.api_key_service import ApiKeyGenerator


@pytest.mark.unit
class TestApiKeyUseCase:
    """API Key Use Case 测试"""

    @pytest.mark.asyncio
    async def test_create_api_key(self):
        """测试: 创建 API Key"""
        # Arrange
        db = AsyncMock()
        repo = AsyncMock()

        # 使用真实的 ApiKeyGenerator 来获取加密密钥
        test_secret = "test-secret-for-encryption"
        encryption_key = ApiKeyGenerator.derive_encryption_key(test_secret)
        generator = ApiKeyGenerator(encryption_key=encryption_key)

        plain_key = "sk_test1234567890123456_abcdefghijklmnopqrstuvwxyz"
        key_id = "test1234567890"
        key_hash = "$2b$hashed"

        # 模拟 generate 方法
        generator.generate = lambda: (plain_key, key_id, key_hash)
        generator.hash_key = lambda _: key_hash
        generator.verify_key = lambda _k, _h: True

        # 模拟 repo.create 返回模型
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        mock_model.user_id = uuid.uuid4()
        mock_model.key_hash = key_hash
        mock_model.key_id = key_id
        mock_model.key_prefix = "sk_"
        mock_model.name = "Test Key"
        mock_model.description = "Test"
        mock_model.scopes = ["agent:read"]
        mock_model.expires_at = datetime.now(UTC) + timedelta(days=90)
        mock_model.is_active = True
        mock_model.last_used_at = None
        mock_model.usage_count = 0
        mock_model.created_at = datetime.now(UTC)
        mock_model.updated_at = datetime.now(UTC)

        repo.create.return_value = mock_model

        use_case = ApiKeyUseCase(db, repo=repo, generator=generator, encryption_key=encryption_key)

        request = ApiKeyCreateRequest(
            name="Test Key",
            description="Test",
            scopes=[ApiKeyScope.AGENT_READ],
            expires_in_days=90,
        )

        # Act
        entity, returned_key = await use_case.create_api_key(
            user_id=uuid.uuid4(),
            request=request,
        )

        # Assert
        assert entity.name == "Test Key"
        assert entity.scopes == {ApiKeyScope.AGENT_READ}
        assert returned_key == plain_key
        assert repo.create.called

    @pytest.mark.asyncio
    async def test_verify_api_key_success(self):
        """测试: 验证 API Key 成功"""
        # Arrange
        db = AsyncMock()
        repo = AsyncMock()

        test_secret = "test-secret-for-encryption"
        encryption_key = ApiKeyGenerator.derive_encryption_key(test_secret)
        generator = MagicMock()

        key_id = "test123456789012"  # 16 字符，符合 KEY_ID_LENGTH
        plain_key = f"sk_{key_id}_abcdefghijklmnopqrstuvwxyz"
        key_hash = "$argon2id$v=19$m=65536,t=3,p=4$test$test"
        user_id = uuid.uuid4()

        generator.generate.return_value = (plain_key, key_id, key_hash)
        generator.is_valid_key_format.return_value = True
        generator.verify_key.return_value = True

        # 模拟 API Key 模型
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        mock_model.user_id = user_id
        mock_model.key_hash = key_hash
        mock_model.key_id = key_id
        mock_model.key_prefix = "sk_"
        mock_model.name = "Test Key"
        mock_model.description = None
        mock_model.scopes = ["agent:read"]
        mock_model.expires_at = datetime.now(UTC) + timedelta(days=90)
        mock_model.is_active = True
        mock_model.last_used_at = None
        mock_model.usage_count = 0
        mock_model.created_at = datetime.now(UTC)
        mock_model.updated_at = datetime.now(UTC)

        repo.get_by_key_id.return_value = [mock_model]

        use_case = ApiKeyUseCase(db, repo=repo, generator=generator, encryption_key=encryption_key)

        # Act
        entity = await use_case.verify_api_key(plain_key)

        # Assert
        assert entity is not None
        assert entity.user_id == user_id
        assert generator.verify_key.called
        # is_valid_key_format 在 domain_service 上调用，不是 generator
        repo.get_by_key_id.assert_called_once_with(key_id)

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid_format(self):
        """测试: 验证格式无效的 API Key"""
        # Arrange
        db = AsyncMock()
        repo = AsyncMock()

        test_secret = "test-secret-for-encryption"
        encryption_key = ApiKeyGenerator.derive_encryption_key(test_secret)
        generator = MagicMock()
        generator.is_valid_key_format.return_value = False

        use_case = ApiKeyUseCase(db, repo=repo, generator=generator, encryption_key=encryption_key)

        # Act
        entity = await use_case.verify_api_key("invalid_key")

        # Assert
        assert entity is None
        assert repo.get_by_key_id.called is False

    @pytest.mark.asyncio
    async def test_verify_api_key_expired(self):
        """测试: 验证已过期的 API Key"""
        # Arrange
        db = AsyncMock()
        repo = AsyncMock()

        test_secret = "test-secret-for-encryption"
        encryption_key = ApiKeyGenerator.derive_encryption_key(test_secret)
        generator = MagicMock()

        key_id = "test123456789012"  # 16 字符，符合 KEY_ID_LENGTH
        plain_key = f"sk_{key_id}_abcdefghijklmnopqrstuvwxyz"
        key_hash = "$argon2id$v=19$m=65536,t=3,p=4$test$test"

        generator.is_valid_key_format.return_value = True
        generator.verify_key.return_value = True

        # 模拟已过期的 API Key
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        mock_model.user_id = uuid.uuid4()
        mock_model.key_hash = key_hash
        mock_model.key_id = key_id
        mock_model.key_prefix = "sk_"
        mock_model.name = "Test Key"
        mock_model.description = None
        mock_model.scopes = ["agent:read"]
        mock_model.expires_at = datetime.now(UTC) - timedelta(days=1)  # 已过期
        mock_model.is_active = True
        mock_model.last_used_at = None
        mock_model.usage_count = 0
        mock_model.created_at = datetime.now(UTC)
        mock_model.updated_at = datetime.now(UTC)

        repo.get_by_key_id.return_value = [mock_model]

        use_case = ApiKeyUseCase(db, repo=repo, generator=generator, encryption_key=encryption_key)

        # Act
        entity = await use_case.verify_api_key(plain_key)

        # Assert
        # 应该返回实体，但 is_valid 为 False
        assert entity is not None
        assert entity.is_valid is False

    @pytest.mark.asyncio
    async def test_revoke_api_key(self):
        """测试: 撤销 API Key"""
        # Arrange
        db = AsyncMock()
        repo = AsyncMock()

        test_secret = "test-secret-for-encryption"
        encryption_key = ApiKeyGenerator.derive_encryption_key(test_secret)
        generator = MagicMock()

        api_key_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # 模拟 get_by_id 返回实体
        mock_entity = MagicMock(
            id=api_key_id,
            user_id=user_id,
            is_active=True,
        )
        repo.get_by_id.return_value = mock_entity
        repo.update.return_value = MagicMock(is_active=False)

        use_case = ApiKeyUseCase(db, repo=repo, generator=generator, encryption_key=encryption_key)

        # Act
        await use_case.revoke_api_key(api_key_id, user_id)

        # Assert
        repo.update.assert_called_once_with(api_key_id, is_active=False)

    @pytest.mark.asyncio
    async def test_delete_api_key(self):
        """测试: 删除 API Key"""
        # Arrange
        db = AsyncMock()
        repo = AsyncMock()

        test_secret = "test-secret-for-encryption"
        encryption_key = ApiKeyGenerator.derive_encryption_key(test_secret)
        generator = MagicMock()

        api_key_id = uuid.uuid4()
        user_id = uuid.uuid4()

        repo.get_by_id.return_value = MagicMock(id=api_key_id, user_id=user_id)
        repo.delete.return_value = True

        use_case = ApiKeyUseCase(db, repo=repo, generator=generator, encryption_key=encryption_key)

        # Act
        await use_case.delete_api_key(api_key_id, user_id)

        # Assert
        repo.delete.assert_called_once_with(api_key_id)

    @pytest.mark.asyncio
    async def test_record_usage(self):
        """测试: 记录 API Key 使用"""
        # Arrange
        db = AsyncMock()
        repo = AsyncMock()

        test_secret = "test-secret-for-encryption"
        encryption_key = ApiKeyGenerator.derive_encryption_key(test_secret)
        generator = MagicMock()

        api_key_id = uuid.uuid4()

        use_case = ApiKeyUseCase(db, repo=repo, generator=generator, encryption_key=encryption_key)

        # Act
        await use_case.record_usage(
            api_key_id=api_key_id,
            endpoint="/api/v1/agents",
            method="GET",
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
            status_code=200,
            response_time_ms=150,
        )

        # Assert
        repo.record_usage.assert_called_once_with(api_key_id)
        repo.create_usage_log.assert_called_once()
