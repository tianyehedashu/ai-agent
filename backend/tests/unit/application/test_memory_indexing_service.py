"""MemoryIndexingService 单测（mock 端口）。"""

from unittest.mock import AsyncMock

import pytest

from domains.agent.application.memory_indexing_service import MemoryIndexingService
from domains.agent.application.ports.vector_index_port import VectorHit


class _FakeEmbedding:
    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


@pytest.mark.unit
class TestMemoryIndexingService:
    @pytest.fixture
    def service(self) -> MemoryIndexingService:
        index = AsyncMock()
        index.ensure_collection = AsyncMock()
        index.upsert_vectors = AsyncMock()
        index.search_vectors = AsyncMock(
            return_value=[
                VectorHit(
                    id="m1",
                    score=0.9,
                    text="hello",
                    payload={"session_id": "s1", "memory_type": "fact"},
                )
            ]
        )
        index.delete_vectors = AsyncMock()
        return MemoryIndexingService(_FakeEmbedding(), index)

    async def test_index_memory_calls_embed_and_upsert(
        self, service: MemoryIndexingService
    ) -> None:
        await service.index_memory(
            session_id="s1",
            memory_id="m1",
            memory_type="fact",
            content="hello world",
        )
        service._index.upsert_vectors.assert_awaited_once()
        call = service._index.upsert_vectors.await_args
        assert call is not None
        assert call.kwargs["point_id"] == "m1"
        assert call.kwargs["vector"] == [0.1, 0.2, 0.3]
        assert call.kwargs["payload"]["text"] == "hello world"

    async def test_search_memories(self, service: MemoryIndexingService) -> None:
        hits = await service.search_memories(session_id="s1", query="hi", limit=5)
        assert len(hits) == 1
        assert hits[0].id == "m1"
        service._index.search_vectors.assert_awaited_once()

    async def test_delete_memory_vectors(self, service: MemoryIndexingService) -> None:
        await service.delete_memory_vectors(memory_id="m1")
        service._index.delete_vectors.assert_awaited_once_with(
            "memories",
            point_ids=["m1"],
        )
