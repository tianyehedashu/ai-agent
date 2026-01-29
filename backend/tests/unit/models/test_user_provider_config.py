"""
UserProviderConfig 模型单元测试

TDD Cycle 1-2: UserProviderConfig 模型
"""

import uuid

import pytest

# 预先导入所有模型以初始化 SQLAlchemy 注册表
from domains.agent.infrastructure.models import Agent, Memory, Session  # noqa: F401
from domains.agent.infrastructure.models.user_provider_config import UserProviderConfig


@pytest.mark.unit
class TestUserProviderConfig:
    """UserProviderConfig 模型测试"""

    def test_create_user_provider_config(self):
        """测试: 创建用户提供商配置"""
        # Arrange
        user_id = uuid.uuid4()

        # Act
        config = UserProviderConfig(
            user_id=user_id,
            provider="dashscope",
            api_key="encrypted_key_value",
            is_active=True,  # 显式设置，DB 层默认值需集成测试验证
        )

        # Assert
        assert config.user_id == user_id
        assert config.provider == "dashscope"
        assert config.api_key == "encrypted_key_value"
        assert config.is_active is True
        assert config.api_base is None  # 可选字段

    def test_create_user_provider_config_with_api_base(self):
        """测试: 创建带自定义 API Base 的配置"""
        # Arrange
        user_id = uuid.uuid4()
        custom_base = "https://custom.api.example.com/v1"

        # Act
        config = UserProviderConfig(
            user_id=user_id,
            provider="openai",
            api_key="sk-xxx",
            api_base=custom_base,
        )

        # Assert
        assert config.api_base == custom_base

    def test_create_user_provider_config_inactive(self):
        """测试: 创建禁用状态的配置"""
        # Arrange
        user_id = uuid.uuid4()

        # Act
        config = UserProviderConfig(
            user_id=user_id,
            provider="anthropic",
            api_key="sk-ant-xxx",
            is_active=False,
        )

        # Assert
        assert config.is_active is False

    def test_user_provider_config_repr(self):
        """测试: 模型字符串表示"""
        # Arrange
        config = UserProviderConfig(
            user_id=uuid.uuid4(),
            provider="deepseek",
            api_key="sk-xxx",
        )

        # Act
        repr_str = repr(config)

        # Assert
        assert "UserProviderConfig" in repr_str
        assert "deepseek" in repr_str

    def test_supported_providers(self):
        """测试: 支持的提供商列表"""
        # 验证所有支持的提供商都可以创建配置
        providers = ["openai", "anthropic", "dashscope", "zhipuai", "deepseek", "volcengine"]
        user_id = uuid.uuid4()

        for provider in providers:
            config = UserProviderConfig(
                user_id=user_id,
                provider=provider,
                api_key=f"sk-{provider}-xxx",
                is_active=True,
            )
            assert config.provider == provider
