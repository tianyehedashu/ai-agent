"""记忆向量索引编排：嵌入 + 向量库，业务规则来自 domain policy。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from domains.agent.domain.memory_index_policy import (
    memory_collection_name,
    vector_filter_for_session,
    vector_payload_for_memory,
)

if TYPE_CHECKING:
    from domains.agent.application.ports.text_embedding_port import TextEmbeddingPort
    from domains.agent.application.ports.vector_index_port import VectorHit, VectorIndexPort


class MemoryIndexingService:
    """会话记忆向量索引（SimpleMem / LongTermMemoryStore 共用）。"""

    def __init__(
        self,
        embedding: TextEmbeddingPort,
        index: VectorIndexPort,
    ) -> None:
        self._embedding = embedding
        self._index = index

    async def ensure_session_collection(self, *, dimension: int | None = None) -> None:
        dim = dimension or settings.embedding_dimension
        await self._index.ensure_collection(
            memory_collection_name(purpose="session"),
            dimension=dim,
        )

    async def index_memory(
        self,
        *,
        session_id: str,
        memory_id: str,
        memory_type: str,
        content: str,
        importance: float = 5.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        collection = memory_collection_name(purpose="session")
        payload = vector_payload_for_memory(
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            metadata=metadata,
        )
        vector = await self._embedding.embed(content)
        await self._index.upsert_vectors(
            collection,
            point_id=memory_id,
            vector=vector,
            payload=payload,
        )

    async def search_memories(
        self,
        *,
        session_id: str,
        query: str,
        limit: int = 10,
    ) -> list[VectorHit]:
        collection = memory_collection_name(purpose="session")
        query_vector = await self._embedding.embed(query)
        filt = vector_filter_for_session(session_id) if session_id else None
        return await self._index.search_vectors(
            collection,
            vector=query_vector,
            limit=limit,
            query_filter=filt,
        )

    async def delete_memory_vectors(self, *, memory_id: str) -> None:
        collection = memory_collection_name(purpose="session")
        await self._index.delete_vectors(collection, point_ids=[memory_id])
