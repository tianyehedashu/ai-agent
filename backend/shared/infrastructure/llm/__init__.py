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

from shared.infrastructure.llm.embeddings import (
    APIEmbedding,
    EmbeddingProvider,
    EmbeddingService,
    LocalEmbedding,
)
from shared.infrastructure.llm.gateway import LLMGateway
from shared.infrastructure.llm.image_generator import ImageGenerationResult, ImageGenerator
from shared.infrastructure.llm.prompt_cache import PromptCacheManager, get_prompt_cache_manager
from shared.infrastructure.llm.providers import (
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
    from shared.interfaces import ImageGeneratorConfigProtocol, LLMConfigProtocol

__all__ = [
    # Embedding Service（本地 + API 统一接口）
    "APIEmbedding",
    # Factory functions
    "create_embedding_service_from_settings",
    "create_image_generator",
    "create_llm_gateway",
    # Gateway
    "EmbeddingProvider",
    "EmbeddingService",
    # Image Generator
    "ImageGenerationResult",
    "ImageGenerator",
    "LLMGateway",
    "LocalEmbedding",
    # Prompt Cache
    "PromptCacheManager",
    # Providers
    "AnthropicProvider",
    "DashScopeProvider",
    "DeepSeekProvider",
    "OpenAIProvider",
    "VolcEngineProvider",
    "ZhipuAIProvider",
    # Utils
    "get_all_models",
    "get_prompt_cache_manager",
    "get_provider",
]


def create_llm_gateway(config: "LLMConfigProtocol") -> LLMGateway:
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


def create_image_generator(config: "ImageGeneratorConfigProtocol") -> ImageGenerator:
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


def create_embedding_service_from_settings() -> EmbeddingService:
    """
    从应用配置创建 EmbeddingService 实例

    这是一个工厂函数，用于在应用层创建 EmbeddingService，
    避免 Core 层直接依赖应用层配置。

    读取配置中的 embedding_provider, embedding_model, embedding_dimension

    Returns:
        EmbeddingService 实例
    """
    from bootstrap.config import settings

    provider = getattr(settings, "embedding_provider", "api")
    model = getattr(settings, "embedding_model", "text-embedding-3-small")
    dimension = getattr(settings, "embedding_dimension", 1536)

    # 获取 API 配置
    api_key = None
    api_base = None

    if provider == "api":
        # 根据模型名称确定 API 配置
        model_lower = model.lower()
        if ("text-embedding" in model_lower or "ada" in model_lower) and settings.openai_api_key:
            key = settings.openai_api_key
            api_key = key.get_secret_value() if hasattr(key, "get_secret_value") else key
            api_base = settings.openai_api_base
        elif "doubao-embedding" in model_lower and settings.volcengine_api_key:
            key = settings.volcengine_api_key
            api_key = key.get_secret_value() if hasattr(key, "get_secret_value") else key
            api_base = settings.volcengine_api_base

    return EmbeddingService(
        provider=provider,
        model=model,
        api_key=api_key,
        api_base=api_base,
        dimension=dimension,
    )
