"""
LLM Server 单元测试 - TDD

测试使用 FastMCP 实现的 LLM Server
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 未安装 mcp 时跳过本模块；安装后预加载 mcp_server 子包，使 patch("...mcp_server.servers.llm_server...") 能解析
pytest.importorskip("mcp")
import domains.agent.infrastructure.mcp_server  # noqa: F401


class TestLLMServerTools:
    """LLM Server 工具测试"""

    @pytest.mark.asyncio
    async def test_llm_create_returns_content(self):
        """llm_create 工具应返回 LLM 生成的内容"""
        # Arrange
        mock_response = MagicMock()
        mock_response.content = "Hello, world!"

        with (
            patch(
                "domains.agent.infrastructure.mcp_server.servers.llm_server.get_llm_config",
                return_value=MagicMock(),
            ),
            patch(
                "domains.agent.infrastructure.mcp_server.servers.llm_server.LLMGateway"
            ) as MockGateway,
        ):
            mock_gateway_instance = AsyncMock()
            mock_gateway_instance.chat = AsyncMock(return_value=mock_response)
            MockGateway.return_value = mock_gateway_instance

            # Act - 调用 llm_create 工具
            from domains.agent.infrastructure.mcp_server.servers.llm_server import (
                llm_create,
            )

            result = await llm_create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hi"}],
            )

            # Assert
            assert result == "Hello, world!"
            mock_gateway_instance.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_create_returns_empty_on_none_content(self):
        """llm_create 工具在 content 为 None 时应返回空字符串"""
        # Arrange
        mock_response = MagicMock()
        mock_response.content = None

        with (
            patch(
                "domains.agent.infrastructure.mcp_server.servers.llm_server.get_llm_config",
                return_value=MagicMock(),
            ),
            patch(
                "domains.agent.infrastructure.mcp_server.servers.llm_server.LLMGateway"
            ) as MockGateway,
        ):
            mock_gateway_instance = AsyncMock()
            mock_gateway_instance.chat = AsyncMock(return_value=mock_response)
            MockGateway.return_value = mock_gateway_instance

            # Act
            from domains.agent.infrastructure.mcp_server.servers.llm_server import (
                llm_create,
            )

            result = await llm_create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hi"}],
            )

            # Assert
            assert result == ""

    @pytest.mark.asyncio
    async def test_llm_list_models_returns_configured_providers(self):
        """llm_list_models 应返回当前已配置 API Key 的提供商及其模型"""
        mock_config = MagicMock()
        mock_config.openai_api_key = None
        mock_config.anthropic_api_key = None
        mock_config.dashscope_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.volcengine_api_key = None
        mock_config.zhipuai_api_key = None

        with patch(
            "domains.agent.infrastructure.mcp_server.servers.llm_server.get_llm_config",
            return_value=mock_config,
        ):
            from domains.agent.infrastructure.mcp_server.servers.llm_server import (
                llm_list_models,
            )

            result = await llm_list_models()

        assert isinstance(result, dict)
        for provider_name, models in result.items():
            assert isinstance(provider_name, str)
            assert isinstance(models, list)
            for item in models:
                assert "id" in item
                assert "name" in item

    @pytest.mark.asyncio
    async def test_llm_list_models_includes_openai_when_configured(self):
        """当配置了 OpenAI API Key 时，llm_list_models 应包含 openai 及其模型"""
        mock_config = MagicMock()
        mock_config.openai_api_key = "sk-test"
        mock_config.anthropic_api_key = None
        mock_config.dashscope_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.volcengine_api_key = None
        mock_config.zhipuai_api_key = None

        with patch(
            "domains.agent.infrastructure.mcp_server.servers.llm_server.get_llm_config",
            return_value=mock_config,
        ):
            from domains.agent.infrastructure.mcp_server.servers.llm_server import (
                llm_list_models,
            )

            result = await llm_list_models()

        assert "openai" in result
        assert isinstance(result["openai"], list)
        assert len(result["openai"]) > 0
        assert result["openai"][0]["id"] in (
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
        )
        assert "name" in result["openai"][0]


class TestLLMServerInstance:
    """LLM Server 实例测试"""

    def test_server_has_correct_name(self):
        """LLM Server 应有正确的名称"""
        from domains.agent.infrastructure.mcp_server.servers.llm_server import (
            llm_server,
        )

        assert llm_server.name == "AI Agent LLM Server"

    def test_server_has_tools_registered(self):
        """LLM Server 应注册了工具"""
        from domains.agent.infrastructure.mcp_server.servers.llm_server import (
            llm_server,
        )

        # FastMCP 的 _tool_manager 包含注册的工具
        assert llm_server._tool_manager is not None


class TestLLMCreateParameters:
    """llm_create 参数测试"""

    @pytest.mark.asyncio
    async def test_llm_create_uses_default_values(self):
        """llm_create 应使用默认参数值"""
        mock_response = MagicMock()
        mock_response.content = "Response"

        with (
            patch(
                "domains.agent.infrastructure.mcp_server.servers.llm_server.get_llm_config",
                return_value=MagicMock(),
            ),
            patch(
                "domains.agent.infrastructure.mcp_server.servers.llm_server.LLMGateway"
            ) as MockGateway,
        ):
            mock_gateway_instance = AsyncMock()
            mock_gateway_instance.chat = AsyncMock(return_value=mock_response)
            MockGateway.return_value = mock_gateway_instance

            from domains.agent.infrastructure.mcp_server.servers.llm_server import (
                llm_create,
            )

            # 只传必需参数
            await llm_create(messages=[{"role": "user", "content": "Hi"}])

            # 验证调用时使用了默认值
            call_kwargs = mock_gateway_instance.chat.call_args.kwargs
            assert call_kwargs.get("model") == "gpt-4"
            assert call_kwargs.get("temperature") == 0.7
            assert call_kwargs.get("max_tokens") == 4096

    @pytest.mark.asyncio
    async def test_llm_create_passes_custom_parameters(self):
        """llm_create 应传递自定义参数"""
        mock_response = MagicMock()
        mock_response.content = "Response"

        with (
            patch(
                "domains.agent.infrastructure.mcp_server.servers.llm_server.get_llm_config",
                return_value=MagicMock(),
            ),
            patch(
                "domains.agent.infrastructure.mcp_server.servers.llm_server.LLMGateway"
            ) as MockGateway,
        ):
            mock_gateway_instance = AsyncMock()
            mock_gateway_instance.chat = AsyncMock(return_value=mock_response)
            MockGateway.return_value = mock_gateway_instance

            from domains.agent.infrastructure.mcp_server.servers.llm_server import (
                llm_create,
            )

            await llm_create(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.5,
                max_tokens=2048,
            )

            # 验证自定义参数被传递
            call_kwargs = mock_gateway_instance.chat.call_args.kwargs
            assert call_kwargs.get("model") == "claude-3-opus"
            assert call_kwargs.get("temperature") == 0.5
            assert call_kwargs.get("max_tokens") == 2048
