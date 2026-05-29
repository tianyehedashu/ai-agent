"""QdrantVectorIndex 适配 qdrant-client 1.16+ query_points API。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client.models import NearestQuery

from libs.db.vector import QdrantVectorIndex


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_vectors_uses_query_points() -> None:
    index = QdrantVectorIndex(url="http://localhost:6333")
    scored = MagicMock()
    scored.id = "pt-1"
    scored.score = 0.91
    scored.payload = {"text": "hello memory"}
    response = MagicMock()
    response.points = [scored]

    client = AsyncMock()
    client.query_points = AsyncMock(return_value=response)
    index._client = client

    hits = await index.search_vectors(
        "session_memories",
        vector=[0.1, 0.2],
        limit=3,
        query_filter={"session_id": "sess-1"},
    )

    client.query_points.assert_awaited_once()
    kwargs = client.query_points.await_args.kwargs
    assert kwargs["collection_name"] == "session_memories"
    assert isinstance(kwargs["query"], NearestQuery)
    assert kwargs["limit"] == 3
    assert len(hits) == 1
    assert hits[0].id == "pt-1"
    assert hits[0].text == "hello memory"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_collection_recreates_on_dimension_mismatch() -> None:
    index = QdrantVectorIndex(url="http://localhost:6333")
    existing = SimpleNamespace(
        config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=512)))
    )
    coll = SimpleNamespace(name="session_memories")
    client = AsyncMock()
    client.get_collections = AsyncMock(
        return_value=MagicMock(collections=[coll])
    )
    client.get_collection = AsyncMock(return_value=existing)
    client.delete_collection = AsyncMock()
    client.create_collection = AsyncMock()
    index._client = client

    await index.ensure_collection("session_memories", dimension=1024)

    client.delete_collection.assert_awaited_once_with(collection_name="session_memories")
    client.create_collection.assert_awaited_once()
    kwargs = client.create_collection.await_args.kwargs
    assert kwargs["collection_name"] == "session_memories"
    assert kwargs["vectors_config"].size == 1024
