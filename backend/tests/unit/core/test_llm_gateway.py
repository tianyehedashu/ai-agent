"""
LLM Gateway 单元测试

使用 Mock 测试 LLM Gateway 的功能
"""

from unittest.mock import patch

import pytest

from domains.agent.domain.types import ToolCall
from domains.agent.infrastructure.llm.gateway import LLMGateway, LLMResponse


class TestLLMGateway:
    """LLM Gateway 测试"""

    @pytest.fixture
    def gateway(self):
        """创建被测对象"""
        from bootstrap.config import settings

        return LLMGateway(config=settings)

    @pytest.mark.asyncio
    async def test_chat_returns_text_response(self, gateway):
        """测试: 返回文本响应"""
        # Arrange
        mock_response = LLMResponse(content="Hello, how can I help?")

        with patch.object(gateway, "_chat", return_value=mock_response):
            # Act
            result = await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4",
            )

            # Assert
            assert result.content == "Hello, how can I help?"
            assert result.tool_calls is None

    @pytest.mark.asyncio
    async def test_chat_parses_tool_calls(self, gateway):
        """测试: 解析工具调用"""
        # Arrange
        tool_call = ToolCall(
            id="call_123",
            name="read_file",
            arguments={"path": "/tmp/test.txt"},
        )
        mock_response = LLMResponse(
            content="",
            tool_calls=[tool_call],
        )

        with patch.object(gateway, "_chat", return_value=mock_response):
            # Act
            result = await gateway.chat(
                messages=[{"role": "user", "content": "Read the file"}],
                model="gpt-4",
                tools=[{"type": "function", "function": {"name": "read_file"}}],
            )

            # Assert
            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "read_file"
            assert result.tool_calls[0].arguments["path"] == "/tmp/test.txt"

    @pytest.mark.asyncio
    async def test_chat_handles_api_error(self, gateway):
        """测试: API 错误处理"""
        # Arrange
        with patch.object(gateway, "_chat", side_effect=Exception("API Error")):
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await gateway.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="gpt-4",
                )

            assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_with_streaming(self, gateway):
        """测试: 流式响应"""
        # Arrange
        from domains.agent.infrastructure.llm.gateway import StreamChunk

        async def mock_stream(**kwargs):
            chunks = [
                StreamChunk(content="Hello"),
                StreamChunk(content=" world"),
                StreamChunk(content="!"),
            ]
            for chunk in chunks:
                yield chunk

        # side_effect 应该返回异步生成器，而不是函数
        with patch.object(gateway, "_stream_chat", return_value=mock_stream()):
            # Act
            # chat() 在 stream=True 时返回协程，需要先 await 得到异步生成器
            stream_generator = await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4",
                stream=True,
            )
            full_content = ""
            async for chunk in stream_generator:
                full_content += chunk.content or ""

            # Assert
            assert full_content == "Hello world!"

    @pytest.mark.asyncio
    async def test_chat_uses_default_model(self, gateway):
        """测试: 使用默认模型"""
        # Arrange
        mock_response = LLMResponse(content="Response")

        with patch.object(gateway, "_chat", return_value=mock_response):
            # Act
            await gateway.chat(messages=[{"role": "user", "content": "Hi"}])

            # Assert
            # 应该使用默认模型
            gateway._chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_temperature(self, gateway):
        """测试: 温度参数传递"""
        # Arrange
        mock_response = LLMResponse(content="Response")

        with patch.object(gateway, "_chat", return_value=mock_response):
            # Act
            await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.5,
            )

            # Assert
            gateway._chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_api_key_glm(self, gateway, monkeypatch):
        """测试: 获取 GLM 模型的 API Key"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings
        monkeypatch.setattr(settings, "zhipuai_api_key", SecretStr("test-key"))
        monkeypatch.setattr(settings, "zhipuai_api_base", "https://open.bigmodel.cn/api/paas/v4")

        # Act
        api_config = gateway._get_api_key("glm-4.7")

        # Assert
        assert "api_key" in api_config
        assert "api_base" in api_config
        assert api_config["api_base"] == "https://open.bigmodel.cn/api/paas/v4"
        assert api_config["api_key"] == "test-key"

    @pytest.mark.asyncio
    async def test_get_api_key_glm_case_insensitive(self, gateway, monkeypatch):
        """测试: GLM 模型名称大小写不敏感"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings
        monkeypatch.setattr(settings, "zhipuai_api_key", SecretStr("test-key"))
        monkeypatch.setattr(settings, "zhipuai_api_base", "https://open.bigmodel.cn/api/paas/v4")

        # Act - 测试不同大小写
        api_config1 = gateway._get_api_key("GLM-4.7")
        api_config2 = gateway._get_api_key("glm-4.7")
        api_config3 = gateway._get_api_key("Glm-4.7")

        # Assert - 都应该返回相同的配置
        assert api_config1 == api_config2 == api_config3
        assert "api_key" in api_config1
        assert api_config1["api_key"] == "test-key"

    @pytest.mark.asyncio
    async def test_get_api_key_glm_no_key(self, gateway, monkeypatch):
        """测试: GLM 模型未配置 API Key 时返回空配置"""
        from bootstrap.config import settings

        # Mock settings - 没有API Key
        monkeypatch.setattr(settings, "zhipuai_api_key", None)

        # Act
        api_config = gateway._get_api_key("glm-4.7")

        # Assert
        assert api_config == {}

    # ========================================================================
    # DeepSeek 测试
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_api_key_deepseek(self, gateway, monkeypatch):
        """测试: 获取 DeepSeek 模型的 API Key"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings
        monkeypatch.setattr(settings, "deepseek_api_key", SecretStr("test-deepseek-key"))
        monkeypatch.setattr(settings, "deepseek_api_base", "https://api.deepseek.com")

        # Act
        api_config = gateway._get_api_key("deepseek-chat")

        # Assert
        assert "api_key" in api_config
        assert "api_base" in api_config
        assert api_config["api_base"] == "https://api.deepseek.com"
        assert api_config["api_key"] == "test-deepseek-key"

    @pytest.mark.asyncio
    async def test_get_api_key_deepseek_case_insensitive(self, gateway, monkeypatch):
        """测试: DeepSeek 模型名称大小写不敏感"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings
        monkeypatch.setattr(settings, "deepseek_api_key", SecretStr("test-deepseek-key"))
        monkeypatch.setattr(settings, "deepseek_api_base", "https://api.deepseek.com")

        # Act - 测试不同大小写
        api_config1 = gateway._get_api_key("DEEPSEEK-chat")
        api_config2 = gateway._get_api_key("deepseek-chat")
        api_config3 = gateway._get_api_key("DeepSeek-chat")

        # Assert - 都应该返回相同的配置
        assert api_config1 == api_config2 == api_config3
        assert "api_key" in api_config1
        assert api_config1["api_key"] == "test-deepseek-key"

    @pytest.mark.asyncio
    async def test_get_api_key_deepseek_no_key(self, gateway, monkeypatch):
        """测试: DeepSeek 模型未配置 API Key 时返回空配置"""
        from bootstrap.config import settings

        # Mock settings - 没有API Key
        monkeypatch.setattr(settings, "deepseek_api_key", None)

        # Act
        api_config = gateway._get_api_key("deepseek-chat")

        # Assert
        assert api_config == {}

    # ========================================================================
    # 火山引擎 (豆包) 测试
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_api_key_volcengine_doubao(self, gateway, monkeypatch):
        """测试: 获取火山引擎豆包模型的 API Key"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings
        monkeypatch.setattr(settings, "volcengine_api_key", SecretStr("test-volcengine-key"))
        monkeypatch.setattr(
            settings, "volcengine_api_base", "https://ark.cn-beijing.volces.com/api/v3"
        )
        monkeypatch.setattr(settings, "volcengine_chat_endpoint_id", "ep-test-chat")

        # Act
        api_config = gateway._get_api_key("doubao-pro")

        # Assert
        assert "api_key" in api_config
        assert "api_base" in api_config
        assert "endpoint_id" in api_config
        assert api_config["api_base"] == "https://ark.cn-beijing.volces.com/api/v3"
        assert api_config["api_key"] == "test-volcengine-key"
        assert api_config["endpoint_id"] == "ep-test-chat"

    @pytest.mark.asyncio
    async def test_get_api_key_volcengine_with_fallback_endpoint(self, gateway, monkeypatch):
        """测试: 火山引擎使用通用 endpoint_id 作为回退"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings - 只有通用 endpoint_id
        monkeypatch.setattr(settings, "volcengine_api_key", SecretStr("test-volcengine-key"))
        monkeypatch.setattr(
            settings, "volcengine_api_base", "https://ark.cn-beijing.volces.com/api/v3"
        )
        monkeypatch.setattr(settings, "volcengine_chat_endpoint_id", None)
        monkeypatch.setattr(settings, "volcengine_endpoint_id", "ep-test-general")

        # Act
        api_config = gateway._get_api_key("doubao-lite")

        # Assert
        assert "endpoint_id" in api_config
        assert api_config["endpoint_id"] == "ep-test-general"

    @pytest.mark.asyncio
    async def test_get_api_key_volcengine_case_insensitive(self, gateway, monkeypatch):
        """测试: 火山引擎模型名称大小写不敏感"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings
        monkeypatch.setattr(settings, "volcengine_api_key", SecretStr("test-volcengine-key"))
        monkeypatch.setattr(
            settings, "volcengine_api_base", "https://ark.cn-beijing.volces.com/api/v3"
        )

        # Act - 测试不同大小写和别名
        api_config1 = gateway._get_api_key("DOUBAO-pro")
        api_config2 = gateway._get_api_key("doubao-pro")
        api_config3 = gateway._get_api_key("volcengine-chat")

        # Assert - 都应该返回相同的配置
        assert api_config1 == api_config2 == api_config3
        assert "api_key" in api_config1
        assert api_config1["api_key"] == "test-volcengine-key"

    @pytest.mark.asyncio
    async def test_get_api_key_volcengine_no_key(self, gateway, monkeypatch):
        """测试: 火山引擎模型未配置 API Key 时返回空配置"""
        from bootstrap.config import settings

        # Mock settings - 没有API Key
        monkeypatch.setattr(settings, "volcengine_api_key", None)

        # Act
        api_config = gateway._get_api_key("doubao-pro")

        # Assert
        assert api_config == {}

    # ========================================================================
    # 阿里云 DashScope (通义千问) 测试
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_api_key_dashscope_qwen(self, gateway, monkeypatch):
        """测试: 获取阿里云 DashScope 通义千问模型的 API Key"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings
        monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-dashscope-key"))
        monkeypatch.setattr(
            settings, "dashscope_api_base", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        # Act
        api_config = gateway._get_api_key("qwen-turbo")

        # Assert
        assert "api_key" in api_config
        assert "api_base" in api_config
        assert api_config["api_base"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert api_config["api_key"] == "test-dashscope-key"

    @pytest.mark.asyncio
    async def test_get_api_key_dashscope_qwen_case_insensitive(self, gateway, monkeypatch):
        """测试: 通义千问模型名称大小写不敏感"""
        from pydantic import SecretStr

        from bootstrap.config import settings

        # Mock settings
        monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-dashscope-key"))
        monkeypatch.setattr(
            settings, "dashscope_api_base", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        # Act - 测试不同大小写
        api_config1 = gateway._get_api_key("QWEN-turbo")
        api_config2 = gateway._get_api_key("qwen-turbo")
        api_config3 = gateway._get_api_key("Qwen-turbo")

        # Assert - 都应该返回相同的配置
        assert api_config1 == api_config2 == api_config3
        assert "api_key" in api_config1
        assert api_config1["api_key"] == "test-dashscope-key"

    @pytest.mark.asyncio
    async def test_get_api_key_dashscope_qwen_no_key(self, gateway, monkeypatch):
        """测试: 通义千问模型未配置 API Key 时返回空配置"""
        from bootstrap.config import settings

        # Mock settings - 没有API Key
        monkeypatch.setattr(settings, "dashscope_api_key", None)

        # Act
        api_config = gateway._get_api_key("qwen-turbo")

        # Assert
        assert api_config == {}

    # ========================================================================
    # 模型能力参数适配 (_adapt_params)
    # ========================================================================

    def test_adapt_params_none_model_info_unchanged(self, gateway):
        """测试: model_info 为 None 时 kwargs 不变"""
        kwargs = {"temperature": 0.5, "response_format": {"type": "json_object"}}
        result = gateway._adapt_params(None, kwargs)
        assert result == kwargs
        assert "response_format" in result

    def test_adapt_params_reasoning_model_removes_response_format(self, gateway):
        """测试: 推理模型移除 response_format，temperature 固定为 1.0"""
        model_info = type("ModelInfo", (), {
            "supports_reasoning": True,
            "supports_json_mode": True,
            "supports_tools": True,
        })()
        kwargs = {"temperature": 0.3, "response_format": {"type": "json_object"}}
        result = gateway._adapt_params(model_info, kwargs)
        assert "response_format" not in result
        assert result["temperature"] == 1.0

    def test_adapt_params_no_json_mode_removes_response_format(self, gateway):
        """测试: supports_json_mode=False 时移除 response_format"""
        model_info = type("ModelInfo", (), {
            "supports_reasoning": False,
            "supports_json_mode": False,
            "supports_tools": True,
        })()
        kwargs = {"temperature": 0.5, "response_format": {"type": "json_object"}}
        result = gateway._adapt_params(model_info, kwargs)
        assert "response_format" not in result
        assert result["temperature"] == 0.5

    def test_adapt_params_no_tools_removes_tools(self, gateway):
        """测试: supports_tools=False 时移除 tools 和 tool_choice"""
        model_info = type("ModelInfo", (), {
            "supports_reasoning": False,
            "supports_json_mode": True,
            "supports_tools": False,
        })()
        kwargs = {"tools": [{"type": "function"}], "tool_choice": "auto"}
        result = gateway._adapt_params(model_info, kwargs)
        assert "tools" not in result
        assert "tool_choice" not in result

    def test_adapt_params_normal_model_keeps_all(self, gateway):
        """测试: 普通模型保留所有参数"""
        model_info = type("ModelInfo", (), {
            "supports_reasoning": False,
            "supports_json_mode": True,
            "supports_tools": True,
        })()
        kwargs = {"temperature": 0.7, "response_format": {"type": "json_object"}, "tools": []}
        result = gateway._adapt_params(model_info, kwargs)
        assert result["response_format"] == {"type": "json_object"}
        assert result["temperature"] == 0.7
        assert "tools" in result

    def test_resolve_model_info_returns_none_for_unknown(self, gateway):
        """测试: 未知模型返回 None"""
        mock_models = type("Models", (), {"get_model": lambda self, m: None})()
        mock_config = type("Config", (), {"models": mock_models})()
        with patch("domains.agent.infrastructure.llm.gateway.get_app_config", return_value=mock_config):
            result = gateway._resolve_model_info("unknown-model", "unknown-model")
        assert result is None
