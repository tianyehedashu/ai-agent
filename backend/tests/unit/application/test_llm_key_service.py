"""
LLMKeyService 单元测试

TDD Cycle 5-12: Key 选择服务、配额检查与扣减
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.agent.application.llm_key_service import (
    LLMKeyService,
    NoKeyConfiguredError,
    QuotaExceededError,
)

# 预先导入所有模型以初始化 SQLAlchemy 注册表
from domains.agent.infrastructure.models import Agent, Memory, Session  # noqa: F401
from domains.agent.infrastructure.models.user_provider_config import UserProviderConfig
from domains.identity.infrastructure.models.quota import UserQuota


@pytest.mark.unit
class TestLLMKeyServiceGetProviderConfig:
    """LLMKeyService.get_provider_config 测试"""

    @pytest.mark.asyncio
    async def test_returns_user_key_when_configured(self):
        """测试: 用户配置了 Key 时返回用户 Key"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 模拟用户已配置 Key
        user_config = MagicMock(spec=UserProviderConfig)
        user_config.api_key = "encrypted_user_key"
        user_config.api_base = None
        user_config.is_active = True
        provider_repo.get_by_user_and_provider.return_value = user_config

        # 模拟解密
        encryptor.decrypt.return_value = "decrypted_user_key"

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act
        api_key, api_base, key_source = await service.get_provider_config(user_id, "dashscope")

        # Assert
        assert api_key == "decrypted_user_key"
        assert api_base is None
        assert key_source == "user"
        provider_repo.get_by_user_and_provider.assert_called_once_with(user_id, "dashscope")
        encryptor.decrypt.assert_called_once_with("encrypted_user_key")

    @pytest.mark.asyncio
    async def test_returns_user_key_with_custom_api_base(self):
        """测试: 用户配置了自定义 API Base 时正确返回"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        user_config = MagicMock(spec=UserProviderConfig)
        user_config.api_key = "encrypted_key"
        user_config.api_base = "https://custom.api.com/v1"
        user_config.is_active = True
        provider_repo.get_by_user_and_provider.return_value = user_config
        encryptor.decrypt.return_value = "user_key"

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act
        api_key, api_base, key_source = await service.get_provider_config(user_id, "openai")

        # Assert
        assert api_key == "user_key"
        assert api_base == "https://custom.api.com/v1"
        assert key_source == "user"

    @pytest.mark.asyncio
    async def test_returns_system_key_when_user_not_configured(self):
        """测试: 用户未配置时返回系统 Key"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 用户未配置
        provider_repo.get_by_user_and_provider.return_value = None

        # 系统 Key
        config.get_provider_api_key.return_value = "system_key"
        config.get_provider_api_base.return_value = "https://api.dashscope.com/v1"

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act
        api_key, api_base, key_source = await service.get_provider_config(user_id, "dashscope")

        # Assert
        assert api_key == "system_key"
        assert api_base == "https://api.dashscope.com/v1"
        assert key_source == "system"

    @pytest.mark.asyncio
    async def test_returns_system_key_when_user_key_inactive(self):
        """测试: 用户 Key 禁用时返回系统 Key"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 用户 Key 已禁用
        user_config = MagicMock(spec=UserProviderConfig)
        user_config.is_active = False
        provider_repo.get_by_user_and_provider.return_value = user_config

        # 系统 Key
        config.get_provider_api_key.return_value = "system_key"
        config.get_provider_api_base.return_value = None

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act
        api_key, _api_base, key_source = await service.get_provider_config(user_id, "openai")

        # Assert
        assert api_key == "system_key"
        assert key_source == "system"

    @pytest.mark.asyncio
    async def test_raises_when_no_key_available(self):
        """测试: 无可用 Key 时抛出 NoKeyConfiguredError"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 用户未配置
        provider_repo.get_by_user_and_provider.return_value = None
        # 系统也未配置
        config.get_provider_api_key.return_value = None

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act & Assert
        with pytest.raises(NoKeyConfiguredError) as exc_info:
            await service.get_provider_config(user_id, "anthropic")

        assert "anthropic" in str(exc_info.value)


@pytest.mark.unit
class TestLLMKeyServiceQuotaCheck:
    """LLMKeyService 配额检查测试"""

    @pytest.mark.asyncio
    async def test_check_quota_passes_when_within_limit(self):
        """测试: 配额未超限时检查通过"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 用户配额: 100 次/天，已用 50 次
        quota = MagicMock(spec=UserQuota)
        quota.daily_text_requests = 100
        quota.current_daily_text = 50
        quota.daily_reset_at = datetime.now(UTC) + timedelta(hours=12)
        quota.needs_daily_reset.return_value = False
        quota_repo.get_by_user.return_value = quota

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act & Assert (不抛异常)
        await service.check_quota(user_id, "text")

    @pytest.mark.asyncio
    async def test_check_quota_fails_when_exceeded(self):
        """测试: 配额超限时抛出 QuotaExceededError"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 用户配额: 100 次/天，已用 100 次
        quota = MagicMock(spec=UserQuota)
        quota.daily_text_requests = 100
        quota.current_daily_text = 100
        quota.daily_reset_at = datetime.now(UTC) + timedelta(hours=12)
        quota.needs_daily_reset.return_value = False
        quota_repo.get_by_user.return_value = quota

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act & Assert
        with pytest.raises(QuotaExceededError) as exc_info:
            await service.check_quota(user_id, "text")

        assert "text" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_quota_passes_when_no_limit(self):
        """测试: 无配额限制时检查通过"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 用户配额: 无限制 (None)
        quota = MagicMock(spec=UserQuota)
        quota.daily_text_requests = None
        quota.current_daily_text = 1000
        quota_repo.get_by_user.return_value = quota

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act & Assert (不抛异常)
        await service.check_quota(user_id, "text")

    @pytest.mark.asyncio
    async def test_check_quota_passes_when_no_quota_record(self):
        """测试: 无配额记录时检查通过（使用默认配额）"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 用户无配额记录
        quota_repo.get_by_user.return_value = None
        # 默认配额
        config.default_daily_text_requests = 50
        config.default_daily_image_requests = 10

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act & Assert (不抛异常，会创建默认配额)
        await service.check_quota(user_id, "text")

    @pytest.mark.asyncio
    async def test_auto_reset_expired_daily_quota(self):
        """测试: 自动重置过期的每日配额"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        # 用户配额: 已过期，需要重置
        quota = MagicMock(spec=UserQuota)
        quota.daily_text_requests = 100
        quota.current_daily_text = 100  # 已用完
        quota.daily_reset_at = datetime.now(UTC) - timedelta(hours=1)  # 已过期
        quota.needs_daily_reset.return_value = True
        quota_repo.get_by_user.return_value = quota

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act & Assert (不抛异常，因为配额会被重置)
        await service.check_quota(user_id, "text")

        # 验证重置被调用
        quota_repo.reset_daily_quota.assert_called_once()


@pytest.mark.unit
class TestLLMKeyServiceDeductQuota:
    """LLMKeyService 配额扣减测试"""

    @pytest.mark.asyncio
    async def test_deduct_quota_increments_counter(self):
        """测试: 扣减配额正确递增计数器"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        quota = MagicMock(spec=UserQuota)
        quota.current_daily_text = 50
        quota_repo.get_by_user.return_value = quota

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act
        await service.deduct_quota(user_id, "text", amount=1)

        # Assert
        quota_repo.increment_usage.assert_called_once_with(user_id, "text", amount=1)

    @pytest.mark.asyncio
    async def test_deduct_quota_with_token_count(self):
        """测试: 按 Token 数扣减配额"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        quota = MagicMock(spec=UserQuota)
        quota_repo.get_by_user.return_value = quota

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act
        await service.deduct_quota(user_id, "text", tokens=1500)

        # Assert
        quota_repo.increment_tokens.assert_called_once_with(user_id, tokens=1500)


@pytest.mark.unit
class TestLLMKeyServiceRecordUsage:
    """LLMKeyService 用量记录测试"""

    @pytest.mark.asyncio
    async def test_record_usage_creates_log(self):
        """测试: 记录用量创建日志"""
        # Arrange
        user_id = uuid.uuid4()
        provider_repo = AsyncMock()
        quota_repo = AsyncMock()
        config = MagicMock()
        encryptor = MagicMock()

        service = LLMKeyService(
            provider_repo=provider_repo,
            quota_repo=quota_repo,
            config=config,
            encryptor=encryptor,
        )

        # Act
        await service.record_usage(
            user_id=user_id,
            capability="text",
            provider="dashscope",
            model="qwen-turbo",
            key_source="system",
            input_tokens=100,
            output_tokens=200,
        )

        # Assert
        quota_repo.create_usage_log.assert_called_once()
        call_kwargs = quota_repo.create_usage_log.call_args[1]
        assert call_kwargs["user_id"] == user_id
        assert call_kwargs["capability"] == "text"
        assert call_kwargs["provider"] == "dashscope"
        assert call_kwargs["model"] == "qwen-turbo"
        assert call_kwargs["key_source"] == "system"
        assert call_kwargs["input_tokens"] == 100
        assert call_kwargs["output_tokens"] == 200
