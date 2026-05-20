"""
Agent LLM 基础设施：经 AI Gateway 桥接的 Facade、Embedding、静态模型目录等。
"""

from typing import TYPE_CHECKING

from domains.agent.infrastructure.llm.agent_llm_facade import (
    AgentLlmFacade,
    AgentLlmResponse,
    AgentStreamChunk,
)
from domains.agent.infrastructure.llm.embeddings import (
    APIEmbedding,
    EmbeddingProvider,
    EmbeddingService,
    LocalEmbedding,
)
from domains.agent.infrastructure.llm.image_generator import ImageGenerationResult, ImageGenerator
from domains.agent.infrastructure.llm.providers import (
    AnthropicProvider,
    DashScopeProvider,
    DeepSeekProvider,
    OpenAIProvider,
    VolcEngineProvider,
    ZhipuAIProvider,
    get_all_models,
    get_configured_models,
    get_provider,
)
from domains.gateway.application.prompt_cache_middleware import (
    PromptCacheMiddleware,
    get_prompt_cache_middleware,
)

get_prompt_cache_manager = get_prompt_cache_middleware
PromptCacheManager = PromptCacheMiddleware

if TYPE_CHECKING:
    from domains.agent.application.ports.model_catalog_port import ModelCatalogPort
    from domains.gateway.application.ports import GatewayProxyProtocol
    from libs.config.interfaces import (
        ImageGeneratorConfigProtocol,
        LLMConfigProtocol,
    )

__all__ = [
    "APIEmbedding",
    "AgentLlmFacade",
    "AgentLlmResponse",
    "AgentStreamChunk",
    "AnthropicProvider",
    "DashScopeProvider",
    "DeepSeekProvider",
    "EmbeddingProvider",
    "EmbeddingService",
    "ImageGenerationResult",
    "ImageGenerator",
    "LocalEmbedding",
    "OpenAIProvider",
    "PromptCacheManager",
    "VolcEngineProvider",
    "ZhipuAIProvider",
    "create_agent_llm_facade",
    "create_embedding_service_from_settings",
    "create_image_generator",
    "get_all_models",
    "get_configured_models",
    "get_prompt_cache_manager",
    "get_provider",
]


def create_agent_llm_facade(
    config: "LLMConfigProtocol",
    gateway_proxy: "GatewayProxyProtocol | None" = None,
    model_catalog: "ModelCatalogPort | None" = None,
) -> AgentLlmFacade:
    """在应用层创建 AgentLlmFacade（经 Gateway 桥接）。"""
    return AgentLlmFacade(
        config=config,
        gateway_proxy=gateway_proxy,
        model_catalog=model_catalog,
    )


def create_image_generator(config: "ImageGeneratorConfigProtocol") -> ImageGenerator:
    """创建 Image Generator 实例。"""
    return ImageGenerator(config=config)


def create_embedding_service_from_settings() -> EmbeddingService:
    """从应用配置创建 EmbeddingService 实例。"""
    from bootstrap.config import settings  # pylint: disable=import-outside-toplevel

    provider = getattr(settings, "embedding_provider", "api")
    model = getattr(settings, "embedding_model", "text-embedding-3-small")
    dimension = getattr(settings, "embedding_dimension", 1536)

    if not isinstance(model, str):
        model = str(model)

    from domains.gateway.application.gateway_proxy_factory import (  # pylint: disable=import-outside-toplevel
        get_gateway_proxy,
    )

    gateway_proxy = get_gateway_proxy()

    return EmbeddingService(
        provider=provider,
        model=model,
        dimension=dimension,
        gateway_proxy=gateway_proxy,
    )
