"""
Embedding Service - 统一的文本向量化服务

支持多种提供商：
- API 提供商（通过 LiteLLM）：OpenAI, 火山引擎, 阿里云等
- 本地模型（CPU 友好）：FastEmbed (BAAI/bge 系列)

最佳实践：
- 生产环境追求质量：使用 OpenAI text-embedding-3-small/large
- 数据敏感/成本控制：使用本地 FastEmbed 模型
- 中文场景：使用 BAAI/bge-small-zh-v1.5 或火山引擎
"""

from abc import ABC, abstractmethod
import asyncio
from typing import Any, Literal

from utils.logging import get_logger

logger = get_logger(__name__)

# 可选依赖：litellm 用于 API 调用
try:
    from litellm import aembedding
except ImportError:
    aembedding = None

# 可选依赖：fastembed 用于本地模型
try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None

# 预定义的本地模型配置
LOCAL_MODELS = {
    # 英文模型
    "bge-small-en": {
        "name": "BAAI/bge-small-en-v1.5",
        "dimension": 384,
        "description": "轻量英文模型，CPU 友好",
    },
    "bge-base-en": {
        "name": "BAAI/bge-base-en-v1.5",
        "dimension": 768,
        "description": "平衡英文模型",
    },
    # 中文模型
    "bge-small-zh": {
        "name": "BAAI/bge-small-zh-v1.5",
        "dimension": 512,
        "description": "轻量中文模型，CPU 友好",
    },
    "bge-base-zh": {
        "name": "BAAI/bge-base-zh-v1.5",
        "dimension": 768,
        "description": "平衡中文模型",
    },
    # 多语言模型
    "bge-m3": {
        "name": "BAAI/bge-m3",
        "dimension": 1024,
        "description": "多语言模型，支持 100+ 语言",
    },
    # 默认模型
    "default": {
        "name": "BAAI/bge-small-en-v1.5",
        "dimension": 384,
        "description": "默认轻量模型",
    },
}


class EmbeddingProvider(ABC):
    """Embedding 提供商抽象基类"""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回向量维度"""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """生成单个文本的嵌入向量"""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本的嵌入向量"""
        ...


class APIEmbedding(EmbeddingProvider):
    """
    API 提供商（通过 LiteLLM 统一接口）

    支持：OpenAI, 火山引擎, 阿里云, 智谱AI 等
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        api_base: str | None = None,
        dimension: int = 1536,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        """通过 API 生成嵌入"""
        if aembedding is None:
            raise ImportError("LiteLLM not installed. Run: pip install litellm")

        kwargs: dict[str, Any] = {"model": self.model, "input": [text]}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        response = await aembedding(**kwargs)
        return response.data[0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量通过 API 生成嵌入"""
        if aembedding is None:
            raise ImportError("LiteLLM not installed. Run: pip install litellm")

        kwargs: dict[str, Any] = {"model": self.model, "input": texts}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        response = await aembedding(**kwargs)
        return [item["embedding"] for item in response.data]


class LocalEmbedding(EmbeddingProvider):
    """
    本地 Embedding（使用 FastEmbed）

    特点：
    - 基于 ONNX Runtime，CPU 友好
    - 无需 GPU，比 sentence-transformers 轻量
    - 支持 BAAI/bge 系列高质量模型
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model = None
        self._dimension: int | None = None

    def _get_model(self):
        """懒加载模型"""
        if self._model is None:
            if TextEmbedding is None:
                raise ImportError("FastEmbed not installed. Run: pip install fastembed")
            logger.info("Loading local embedding model: %s", self.model_name)
            self._model = TextEmbedding(model_name=self.model_name)
            logger.info("Local embedding model loaded successfully")
        return self._model

    @property
    def dimension(self) -> int:
        """获取模型维度"""
        if self._dimension is None:
            # 从预定义配置获取
            for config in LOCAL_MODELS.values():
                if config["name"] == self.model_name:
                    self._dimension = config["dimension"]
                    break
            # 如果未找到，通过实际嵌入获取
            if self._dimension is None:
                model = self._get_model()
                sample = next(iter(model.embed(["test"])))
                self._dimension = len(sample)
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        """生成单个文本的嵌入"""

        model = self._get_model()
        # FastEmbed 是同步的，在线程池中运行
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: next(iter(model.embed([text]))).tolist())
        return result

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入"""

        model = self._get_model()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: [emb.tolist() for emb in model.embed(texts)]
        )
        return result


class EmbeddingService:
    """
    统一的 Embedding 服务

    根据配置自动选择 API 或本地模型

    使用示例:
        # API 模式（默认）
        service = EmbeddingService(provider="api", model="text-embedding-3-small")

        # 本地模式（CPU 友好）
        service = EmbeddingService(provider="local", model="bge-small-zh")

        # 生成嵌入
        vector = await service.embed("Hello world")
        vectors = await service.embed_batch(["Hello", "World"])
    """

    def __init__(
        self,
        provider: Literal["api", "local"] = "api",
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        dimension: int | None = None,
    ):
        """
        初始化 Embedding 服务

        Args:
            provider: 提供商类型 ("api" 或 "local")
            model: 模型名称
                - API 模式: "text-embedding-3-small", "doubao-embedding-*" 等
                - 本地模式: "bge-small-zh", "bge-base-en" 或完整名称
            api_key: API 密钥（仅 API 模式）
            api_base: API 基础 URL（仅 API 模式）
            dimension: 向量维度（可选，自动检测）
        """
        self.provider_type = provider

        if provider == "local":
            # 解析本地模型名称
            if model and model in LOCAL_MODELS:
                model_config = LOCAL_MODELS[model]
                model_name = model_config["name"]
                dimension = dimension or model_config["dimension"]
            else:
                model_name = model or LOCAL_MODELS["default"]["name"]
                dimension = dimension or LOCAL_MODELS["default"]["dimension"]

            self._provider: EmbeddingProvider = LocalEmbedding(model_name=model_name)
            self._dimension = dimension
            logger.info(
                "EmbeddingService initialized with local model: %s (dim=%d)",
                model_name,
                dimension,
            )
        else:
            # API 模式
            model = model or "text-embedding-3-small"
            dimension = dimension or 1536
            self._provider = APIEmbedding(
                model=model,
                api_key=api_key,
                api_base=api_base,
                dimension=dimension,
            )
            self._dimension = dimension
            logger.info(
                "EmbeddingService initialized with API model: %s (dim=%d)",
                model,
                dimension,
            )

    @property
    def dimension(self) -> int:
        """获取向量维度"""
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        """生成单个文本的嵌入向量"""
        return await self._provider.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入向量"""
        return await self._provider.embed_batch(texts)


# 便捷导出
__all__ = [
    "LOCAL_MODELS",
    "APIEmbedding",
    "EmbeddingProvider",
    "EmbeddingService",
    "LocalEmbedding",
]
