"""
向量索引与记忆索引组合根。

- ``get_vector_index``：Qdrant / Chroma 适配器（无嵌入）
- ``build_memory_indexing_service``：嵌入 + 索引编排（应用层）
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from bootstrap.config import settings
from domains.agent.application.memory_indexing_service import MemoryIndexingService
from domains.agent.domain.vector_backend_policy import effective_vector_db_type
from domains.agent.infrastructure.llm import (
    EmbeddingService,
    create_embedding_service_from_catalog,
    create_embedding_service_from_settings,
)
from domains.agent.infrastructure.memory.vector_index_bridge import VectorIndexBridge
from libs.db.vector import ChromaVectorIndex, EphemeralChromaVectorIndex, QdrantVectorIndex

if TYPE_CHECKING:
    from domains.agent.application.ports.text_embedding_port import TextEmbeddingPort
    from domains.agent.application.ports.vector_index_port import VectorIndexPort
    from domains.gateway.application.model_catalog_port import ModelCatalogPort

from utils.logging import get_logger

logger = get_logger(__name__)

_chroma_singleton: ChromaVectorIndex | None = None


class _EmbeddingServiceAdapter:
    def __init__(self, service: EmbeddingService) -> None:
        self._service = service

    async def embed(self, text: str) -> list[float]:
        return await self._service.embed(text)


def create_text_embedding_port() -> TextEmbeddingPort:
    return _EmbeddingServiceAdapter(create_embedding_service_from_settings())


async def create_text_embedding_port_async(
    model_catalog: ModelCatalogPort,
) -> TextEmbeddingPort:
    return _EmbeddingServiceAdapter(await create_embedding_service_from_catalog(model_catalog))


def get_vector_index() -> VectorIndexPort:
    """按配置返回向量索引适配器。"""
    db_type = effective_vector_db_type(
        settings.vector_db_type,
        pytest_chroma_ephemeral=os.environ.get("PYTEST_CHROMA_EPHEMERAL") == "1",
    )

    if db_type == "chroma":
        global _chroma_singleton
        if _chroma_singleton is None:
            if os.environ.get("PYTEST_CHROMA_EPHEMERAL") == "1":
                _chroma_singleton = EphemeralChromaVectorIndex()
            else:
                _chroma_singleton = ChromaVectorIndex(persist_directory=settings.chroma_path)
            logger.debug("vector index: chroma (%s)", type(_chroma_singleton).__name__)
        return VectorIndexBridge(_chroma_singleton)

    return VectorIndexBridge(
        QdrantVectorIndex(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    )


def build_memory_indexing_service(
    *,
    embedding: TextEmbeddingPort | None = None,
    index: VectorIndexPort | None = None,
) -> MemoryIndexingService:
    return MemoryIndexingService(
        embedding=embedding or create_text_embedding_port(),
        index=index or get_vector_index(),
    )


def reset_vector_index() -> None:
    """关闭 Chroma 单例（pytest teardown）。"""
    global _chroma_singleton
    if _chroma_singleton is not None:
        _chroma_singleton.close()
        _chroma_singleton = None


# 兼容旧测试/conftest 命名
reset_vector_store = reset_vector_index
