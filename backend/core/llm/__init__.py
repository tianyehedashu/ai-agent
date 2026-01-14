"""
LLM Gateway - 大语言模型网关

统一多模型接口，支持:
- OpenAI (GPT-4, GPT-4o, o1)
- Anthropic (Claude 3.5)
- 阿里云 DashScope (通义千问 Qwen)
- DeepSeek (deepseek-chat, deepseek-coder, deepseek-reasoner)
- 火山引擎 (字节豆包文本对话 + Seedream图像生成)
- 其他 LiteLLM 支持的模型

图像生成:
- 火山引擎 Seedream (Doubao-Seedream)
- OpenAI DALL-E
"""

from core.llm.gateway import LLMGateway
from core.llm.image_generator import ImageGenerationResult, ImageGenerator
from core.llm.providers import (
    AnthropicProvider,
    DashScopeProvider,
    DeepSeekProvider,
    OpenAIProvider,
    VolcEngineProvider,
    get_all_models,
    get_provider,
)

__all__ = [
    "AnthropicProvider",
    "DashScopeProvider",
    "DeepSeekProvider",
    "ImageGenerationResult",
    "ImageGenerator",
    "LLMGateway",
    "OpenAIProvider",
    "VolcEngineProvider",
    "get_all_models",
    "get_provider",
]
