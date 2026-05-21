"""
LangGraph Store Wrapper - 长期记忆存储

混合架构：
- LangGraph Store：元数据 / JSON 文档
- MemoryIndexingService：语义向量索引（嵌入 + Qdrant/Chroma）
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
import uuid

from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres import PostgresStore

from bootstrap.config import settings
from domains.agent.domain.memory_index_policy import (
    langgraph_namespace,
    langgraph_namespace_candidates,
)
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.agent.application.memory_indexing_service import MemoryIndexingService

logger = get_logger(__name__)


def _create_store_factory(
    store_type: Literal["postgres", "memory"] = "postgres",
):
    if store_type == "postgres":
        db_url = settings.database_url.replace("+asyncpg", "")

        @asynccontextmanager
        async def postgres_store_context():
            holder: dict[str, PostgresStore] = {}
            release = threading.Event()

            def worker() -> None:
                with PostgresStore.from_conn_string(db_url) as store:
                    holder["store"] = store
                    release.wait()

            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            while "store" not in holder:
                await asyncio.sleep(0.01)
            try:
                yield holder["store"]
            finally:
                release.set()
                thread.join(timeout=30.0)

        return postgres_store_context

    if store_type == "memory":

        @asynccontextmanager
        async def memory_store_context():
            yield InMemoryStore()

        return memory_store_context

    raise ValueError(f"Unsupported store type: {store_type}")


class LongTermMemoryStore:
    """长期记忆：LangGraph 元数据 + 向量语义检索。"""

    def __init__(
        self,
        memory_indexing: MemoryIndexingService,
        store_type: Literal["postgres", "memory"] | None = None,
    ) -> None:
        self._indexing = memory_indexing
        store_type = store_type or settings.memory_store_type
        self._store_context_factory = _create_store_factory(store_type)
        self._store_type = store_type
        logger.info("LongTermMemoryStore initialized with %s backend", store_type)

    async def setup(self) -> None:
        async with self._store_context_factory() as store:
            await asyncio.to_thread(store.setup)  # type: ignore[misc]
        await self._indexing.ensure_session_collection()
        logger.info("LongTermMemoryStore initialized")

    async def search(
        self,
        session_id: str,
        query: str,
        limit: int = 10,
        memory_type: str | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        hits = await self._indexing.search_memories(
            session_id=session_id,
            query=query,
            limit=limit * 2,
        )

        logger.debug(
            "Vector search returned %d results for session_id=%s",
            len(hits),
            session_id,
        )

        memories: list[dict[str, Any]] = []
        async with self._store_context_factory() as store:
            for hit in hits:
                memory_id = hit.id
                result_memory_type = hit.payload.get("memory_type")
                if isinstance(result_memory_type, str):
                    pass
                else:
                    result_memory_type = None

                possible_namespaces = langgraph_namespace_candidates(
                    session_id,
                    memory_type=memory_type,
                    result_memory_type=result_memory_type,
                )

                memory_data = None
                for ns in possible_namespaces:
                    memory_data = await asyncio.to_thread(
                        store.get,
                        namespace=ns,
                        key=memory_id,
                    )
                    if memory_data:
                        break

                if not memory_data:
                    logger.warning(
                        "No memory_data found for memory_id=%s in any namespace",
                        memory_id,
                    )
                    continue

                value = memory_data.value
                if memory_type and value.get("type") != memory_type:
                    continue

                flat = hit.as_flat_dict()
                memories.append(
                    {
                        "id": memory_id,
                        "content": value.get("content", hit.text),
                        "type": value.get("type"),
                        "importance": value.get("importance", 0),
                        "metadata": value.get("metadata", {}),
                        "score": flat.get("score", hit.score),
                    }
                )

        memories.sort(key=lambda x: (x["score"], x.get("importance", 0)), reverse=True)
        return memories[:limit]

    async def put(
        self,
        session_id: str,
        memory_type: str,
        content: str,
        importance: float = 5.0,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> str:
        memory_id = str(uuid.uuid4())
        namespace = langgraph_namespace(session_id, memory_type)

        value: dict[str, Any] = {
            "content": content,
            "type": memory_type,
            "importance": importance,
            "metadata": metadata or {},
            "created_at": datetime.now(UTC).isoformat(),
        }

        async with self._store_context_factory() as store:
            await asyncio.to_thread(
                store.put,
                namespace=namespace,
                key=memory_id,
                value=value,
            )

        await self._indexing.index_memory(
            session_id=session_id,
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            metadata=metadata,
        )

        logger.info(
            "Stored memory: %s (session=%s, type=%s, importance=%.1f)",
            memory_id,
            session_id,
            memory_type,
            importance,
        )
        return memory_id

    async def delete(
        self,
        session_id: str,
        memory_id: str,
        memory_type: str,
        user_id: str | None = None,
    ) -> None:
        namespace = langgraph_namespace(session_id, memory_type)

        async with self._store_context_factory() as store:
            await asyncio.to_thread(
                store.delete,
                namespace=namespace,
                key=memory_id,
            )

        await self._indexing.delete_memory_vectors(memory_id=memory_id)
        logger.info("Deleted memory: %s", memory_id)
