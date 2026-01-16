"""
LLM Providers - 模型提供商

提供对特定模型的支持和优化

支持的提供商:
- OpenAI (GPT 系列)
- Anthropic (Claude 系列)
- 阿里云 DashScope (通义千问 Qwen 系列)
- DeepSeek
- 火山引擎 (字节豆包)
- 智谱AI (GLM 系列)
"""

from typing import Any, ClassVar


class BaseProvider:
    """提供商基类"""

    name: ClassVar[str] = "base"
    models: ClassVar[list[str]] = []

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """格式化工具定义"""
        return tools

    def format_tool_result(self, result: str) -> str:
        """格式化工具结果"""
        return result


class OpenAIProvider(BaseProvider):
    """OpenAI 提供商"""

    name: ClassVar[str] = "openai"
    models: ClassVar[list[str]] = [
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-3.5-turbo",
        "o1-preview",
        "o1-mini",
    ]

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """OpenAI 工具格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for tool in tools
        ]


class AnthropicProvider(BaseProvider):
    """Anthropic 提供商"""

    name: ClassVar[str] = "anthropic"
    models: ClassVar[list[str]] = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Anthropic 工具格式"""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
            }
            for tool in tools
        ]


class DashScopeProvider(BaseProvider):
    """
    阿里云 DashScope 提供商 (通义千问)

    支持的模型:
    - qwen-turbo: 速度快，适合简单任务
    - qwen-plus: 平衡性能和成本
    - qwen-max: 最强能力，适合复杂任务
    - qwen-max-longcontext: 支持长上下文
    - qwen-vl-plus: 视觉语言模型
    - qwen-vl-max: 视觉语言模型(增强版)

    文档: https://help.aliyun.com/zh/dashscope/
    """

    name: ClassVar[str] = "dashscope"
    models: ClassVar[list[str]] = [
        "qwen-turbo",
        "qwen-turbo-latest",
        "qwen-plus",
        "qwen-plus-latest",
        "qwen-max",
        "qwen-max-latest",
        "qwen-max-longcontext",
        "qwen-vl-plus",
        "qwen-vl-max",
        "qwen2.5-72b-instruct",
        "qwen2.5-32b-instruct",
        "qwen2.5-14b-instruct",
        "qwen2.5-7b-instruct",
        "qwen2.5-coder-32b-instruct",
    ]

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """DashScope 使用 OpenAI 兼容格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for tool in tools
        ]


class DeepSeekProvider(BaseProvider):
    """
    DeepSeek 提供商

    支持的模型:
    - deepseek-chat: 通用对话模型
    - deepseek-coder: 代码专用模型
    - deepseek-reasoner: 推理增强模型 (DeepSeek-R1)

    文档: https://platform.deepseek.com/docs
    """

    name: ClassVar[str] = "deepseek"
    models: ClassVar[list[str]] = [
        "deepseek-chat",
        "deepseek-coder",
        "deepseek-reasoner",
    ]

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """DeepSeek 使用 OpenAI 兼容格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for tool in tools
        ]


class VolcEngineProvider(BaseProvider):
    """
    火山引擎提供商 (字节跳动豆包)

    支持的模型:
    - doubao-pro-32k: 专业版，32K 上下文
    - doubao-pro-128k: 专业版，128K 上下文
    - doubao-lite-32k: 轻量版，32K 上下文
    - doubao-lite-128k: 轻量版，128K 上下文

    注意: 火山引擎需要配置 endpoint_id

    文档: https://www.volcengine.com/docs/82379
    """

    name: ClassVar[str] = "volcengine"
    models: ClassVar[list[str]] = [
        "doubao-pro-32k",
        "doubao-pro-128k",
        "doubao-pro-256k",
        "doubao-lite-32k",
        "doubao-lite-128k",
        "doubao-character-pro-32k",
    ]

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """火山引擎使用 OpenAI 兼容格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for tool in tools
        ]


class ZhipuAIProvider(BaseProvider):
    """
    智谱AI提供商 (GLM 系列)

    支持的模型:
    - GLM-4.7: 最新版本，支持代码生成和工具调用
    - GLM-4: 通用对话模型
    - GLM-4-Plus: 增强版
    - GLM-4-Air: 轻量版
    - GLM-4-Flash: 快速版

    文档: https://open.bigmodel.cn/
    """

    name: ClassVar[str] = "zhipuai"
    models: ClassVar[list[str]] = [
        "glm-4.7",
        "glm-4",
        "glm-4-plus",
        "glm-4-air",
        "glm-4-flash",
    ]

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """智谱AI使用 OpenAI 兼容格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for tool in tools
        ]


# 提供商注册表
PROVIDERS: dict[str, BaseProvider] = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "dashscope": DashScopeProvider(),
    "deepseek": DeepSeekProvider(),
    "volcengine": VolcEngineProvider(),
    "zhipuai": ZhipuAIProvider(),
}


def get_provider(model: str) -> BaseProvider:
    """根据模型获取提供商"""
    model_lower = model.lower()

    # 模型模式到提供商的映射（按优先级排序）
    # 特殊处理：o1 需要检查前缀
    if model_lower.startswith("o1"):
        return PROVIDERS["openai"]

    # 其他模式检查
    model_patterns = [
        ("claude", "anthropic"),
        ("gpt", "openai"),
        ("qwen", "dashscope"),
        ("deepseek", "deepseek"),
        ("doubao", "volcengine"),
        ("glm", "zhipuai"),
    ]

    for pattern, provider_key in model_patterns:
        if pattern in model_lower:
            return PROVIDERS[provider_key]

    # 默认返回 OpenAI 格式 (大多数兼容)
    return PROVIDERS["openai"]


def get_all_models() -> dict[str, list[str]]:
    """获取所有支持的模型列表"""
    return {provider.name: provider.models for provider in PROVIDERS.values()}
