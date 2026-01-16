"""
LLM Providers 单元测试

测试各个 LLM 提供商的模型列表和工具格式化功能
"""

from core.llm.providers import (
    AnthropicProvider,
    DashScopeProvider,
    DeepSeekProvider,
    OpenAIProvider,
    VolcEngineProvider,
    ZhipuAIProvider,
    get_all_models,
    get_provider,
)


class TestProviders:
    """提供商测试"""

    def test_openai_provider_models(self):
        """测试: OpenAI 提供商模型列表"""
        provider = OpenAIProvider()
        assert "gpt-4" in provider.models
        assert "gpt-4-turbo" in provider.models
        assert "gpt-4o" in provider.models
        assert provider.name == "openai"

    def test_anthropic_provider_models(self):
        """测试: Anthropic 提供商模型列表"""
        provider = AnthropicProvider()
        assert "claude-3-5-sonnet-20241022" in provider.models
        assert "claude-3-opus-20240229" in provider.models
        assert provider.name == "anthropic"

    def test_dashscope_provider_models(self):
        """测试: DashScope 提供商模型列表"""
        provider = DashScopeProvider()
        assert "qwen-max" in provider.models
        assert "qwen-turbo" in provider.models
        assert provider.name == "dashscope"

    def test_deepseek_provider_models(self):
        """测试: DeepSeek 提供商模型列表"""
        provider = DeepSeekProvider()
        assert "deepseek-chat" in provider.models
        assert "deepseek-coder" in provider.models
        assert provider.name == "deepseek"

    def test_volcengine_provider_models(self):
        """测试: 火山引擎提供商模型列表"""
        provider = VolcEngineProvider()
        assert "doubao-pro-32k" in provider.models
        assert "doubao-lite-128k" in provider.models
        assert provider.name == "volcengine"

    def test_zhipuai_provider_models(self):
        """测试: 智谱AI提供商模型列表"""
        provider = ZhipuAIProvider()
        assert "glm-4.7" in provider.models
        assert "glm-4" in provider.models
        assert "glm-4-plus" in provider.models
        assert "glm-4-air" in provider.models
        assert "glm-4-flash" in provider.models
        assert provider.name == "zhipuai"

    def test_zhipuai_provider_format_tools(self):
        """测试: 智谱AI工具格式化"""
        provider = ZhipuAIProvider()
        tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                    },
                },
            }
        ]
        formatted = provider.format_tools(tools)
        assert len(formatted) == 1
        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "read_file"
        assert formatted[0]["function"]["description"] == "Read a file"


class TestGetProvider:
    """获取提供商测试"""

    def test_get_provider_claude(self):
        """测试: 获取 Claude 提供商"""
        provider = get_provider("claude-3-5-sonnet-20241022")
        assert isinstance(provider, AnthropicProvider)

    def test_get_provider_gpt(self):
        """测试: 获取 GPT 提供商"""
        provider = get_provider("gpt-4")
        assert isinstance(provider, OpenAIProvider)

    def test_get_provider_qwen(self):
        """测试: 获取 Qwen 提供商"""
        provider = get_provider("qwen-max")
        assert isinstance(provider, DashScopeProvider)

    def test_get_provider_deepseek(self):
        """测试: 获取 DeepSeek 提供商"""
        provider = get_provider("deepseek-chat")
        assert isinstance(provider, DeepSeekProvider)

    def test_get_provider_doubao(self):
        """测试: 获取豆包提供商"""
        provider = get_provider("doubao-pro-32k")
        assert isinstance(provider, VolcEngineProvider)

    def test_get_provider_glm(self):
        """测试: 获取 GLM 提供商"""
        provider = get_provider("glm-4.7")
        assert isinstance(provider, ZhipuAIProvider)

        provider = get_provider("GLM-4")
        assert isinstance(provider, ZhipuAIProvider)

        provider = get_provider("glm-4-plus")
        assert isinstance(provider, ZhipuAIProvider)

    def test_get_provider_default(self):
        """测试: 获取默认提供商"""
        provider = get_provider("unknown-model")
        assert isinstance(provider, OpenAIProvider)  # 默认返回 OpenAI 格式


class TestGetAllModels:
    """获取所有模型测试"""

    def test_get_all_models_structure(self):
        """测试: 获取所有模型的结构"""
        all_models = get_all_models()
        assert isinstance(all_models, dict)
        assert "openai" in all_models
        assert "anthropic" in all_models
        assert "dashscope" in all_models
        assert "deepseek" in all_models
        assert "volcengine" in all_models
        assert "zhipuai" in all_models

    def test_get_all_models_zhipuai(self):
        """测试: 获取智谱AI模型列表"""
        all_models = get_all_models()
        assert "zhipuai" in all_models
        zhipuai_models = all_models["zhipuai"]
        assert "glm-4.7" in zhipuai_models
        assert "glm-4" in zhipuai_models
        assert len(zhipuai_models) >= 5  # 至少包含5个模型
