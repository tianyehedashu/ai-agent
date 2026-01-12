"""
LLM Providers - 模型提供商

提供对特定模型的支持和优化
"""

from typing import Any

from app.config import settings
from core.types import ToolCategory


class BaseProvider:
    """提供商基类"""

    name: str = "base"
    models: list[str] = []

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """格式化工具定义"""
        return tools

    def format_tool_result(self, result: str) -> str:
        """格式化工具结果"""
        return result


class OpenAIProvider(BaseProvider):
    """OpenAI 提供商"""

    name = "openai"
    models = [
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-3.5-turbo",
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

    name = "anthropic"
    models = [
        "claude-3-5-sonnet-20241022",
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


# 提供商注册表
PROVIDERS: dict[str, BaseProvider] = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
}


def get_provider(model: str) -> BaseProvider:
    """根据模型获取提供商"""
    model_lower = model.lower()

    if "claude" in model_lower:
        return PROVIDERS["anthropic"]
    elif "gpt" in model_lower:
        return PROVIDERS["openai"]

    # 默认返回 OpenAI 格式
    return PROVIDERS["openai"]
