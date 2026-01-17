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

Token 优化:
- 提示词缓存 (Prompt Caching)
- 支持 Anthropic/DeepSeek/OpenAI 的缓存 API
"""

from typing import TYPE_CHECKING

from core.llm.embeddings import (
    APIEmbedding,
    EmbeddingProvider,
    EmbeddingService,
    LocalEmbedding,
)
from core.llm.gateway import LLMGateway
from core.llm.image_generator import ImageGenerationResult, ImageGenerator
from core.llm.prompt_cache import PromptCacheManager, get_prompt_cache_manager
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

if TYPE_CHECKING:
    from core.config import ImageGeneratorConfig, LLMConfig

__all__ = [
    # Embedding Service（本地 + API 统一接口）
    "APIEmbedding",
    # Providers
    "AnthropicProvider",
    "DashScopeProvider",
    "DeepSeekProvider",
    "EmbeddingProvider",
    "EmbeddingService",
    # Image Generator
    "ImageGenerationResult",
    "ImageGenerator",
    # Gateway
    "LLMGateway",
    "LocalEmbedding",
    "OpenAIProvider",
    # Prompt Cache
    "PromptCacheManager",
    "VolcEngineProvider",
    "ZhipuAIProvider",
    "create_image_generator",
    "create_llm_gateway",
    # Utils
    "get_all_models",
    "get_prompt_cache_manager",
    "get_provider",
]


def create_llm_gateway(config: "LLMConfig") -> LLMGateway:
    """
    创建 LLM Gateway 实例

    这是一个工厂函数，用于在应用层创建 LLMGateway，
    避免 Core 层直接依赖应用层配置。

    Args:
        config: LLM 配置

    Returns:
        LLMGateway 实例
    """
    return LLMGateway(config=config)


def create_image_generator(config: "ImageGeneratorConfig") -> ImageGenerator:
    """
    创建 Image Generator 实例

    这是一个工厂函数，用于在应用层创建 ImageGenerator，
    避免 Core 层直接依赖应用层配置。

    Args:
        config: 图像生成配置

    Returns:
        ImageGenerator 实例
    """
    return ImageGenerator(config=config)
