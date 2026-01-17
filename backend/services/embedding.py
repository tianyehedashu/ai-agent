"""
Embedding Service Factory - 从配置创建 Embedding 服务

这是一个工厂模块，用于在应用层创建 EmbeddingService，
避免 Core 层直接依赖应用层配置。
"""

from app.config import settings
from core.llm.embeddings import EmbeddingService


def get_embedding_service_from_settings() -> EmbeddingService:
    """
    从应用配置创建 EmbeddingService

    读取配置中的 embedding_provider, embedding_model, embedding_dimension
    """
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
