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

from domains.agent.infrastructure.llm.embeddings import (
    APIEmbedding,
    EmbeddingProvider,
    EmbeddingService,
    LocalEmbedding,
)
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.llm.image_generator import ImageGenerationResult, ImageGenerator
from domains.agent.infrastructure.llm.prompt_cache import (
    PromptCacheManager,
    get_prompt_cache_manager,
)
from domains.agent.infrastructure.llm.providers import (
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
    from libs.config.interfaces import (
        ImageGeneratorConfigProtocol,
        LLMConfigProtocol,
    )

__all__ = [
    # Embedding Service（本地 + API 统一接口）
    "APIEmbedding",
    # Providers
    "AnthropicProvider",
    "DashScopeProvider",
    "DeepSeekProvider",
    # Gateway
    "EmbeddingProvider",
    "EmbeddingService",
    # Image Generator
    "ImageGenerationResult",
    "ImageGenerator",
    "LLMGateway",
    "LocalEmbedding",
    "OpenAIProvider",
    # Prompt Cache
    "PromptCacheManager",
    "VolcEngineProvider",
    "ZhipuAIProvider",
    # Factory functions
    "create_embedding_service_from_settings",
    "create_image_generator",
    "create_llm_gateway",
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
    from bootstrap.config import settings  # pylint: disable=import-outside-toplevel

    provider = getattr(settings, "embedding_provider", "api")
    model = getattr(settings, "embedding_model", "text-embedding-3-small")
    dimension = getattr(settings, "embedding_dimension", 1536)

    # 确保 model 是字符串类型
    if not isinstance(model, str):
        model = str(model)

    # 获取 API 配置
    api_key = None
    api_base = None

    if provider == "api":
        # 根据模型名称确定 API 配置
        model_lower = model.lower()

        # 处理 DashScope 模型（格式：dashscope/text-embedding-v3）
        # 注意：LiteLLM 不支持 DashScope embedding，使用直接 API 调用（OpenAI 兼容模式）
        if "dashscope" in model_lower and settings.dashscope_api_key:
            # 提取实际模型名称（去掉 dashscope/ 前缀）
            if "/" in model:
                model = model.split("/", 1)[1]  # 提取 text-embedding-v3
            key = settings.dashscope_api_key
            api_key = key.get_secret_value() if hasattr(key, "get_secret_value") else key
            # DashScope embedding 使用 OpenAI 兼容模式的 endpoint
            api_base = settings.dashscope_api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        elif ("text-embedding" in model_lower or "ada" in model_lower) and settings.openai_api_key:
            key = settings.openai_api_key
            api_key = key.get_secret_value() if hasattr(key, "get_secret_value") else key
            api_base = settings.openai_api_base
        elif "doubao-embedding" in model_lower and settings.volcengine_api_key:
            # LiteLLM 需要 volcengine/ 前缀
            if not model.startswith("volcengine/"):
                model = f"volcengine/{model}"
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
