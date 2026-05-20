"""向量索引工厂：配置与 pytest 环境选择。"""

import pytest

from bootstrap.config import settings
from domains.agent.infrastructure.memory.vector_index_bridge import VectorIndexBridge
from domains.agent.infrastructure.memory.vector_store_factory import (
    _effective_vector_db_type,
    build_memory_indexing_service,
    get_vector_index,
    reset_vector_index,
)
from libs.db.vector import EphemeralChromaVectorIndex, QdrantVectorIndex


class _FakeEmbedding:
    async def embed(self, text: str) -> list[float]:
        return [0.1] * 4


@pytest.fixture(autouse=True)
def _reset_chroma_singleton():
    reset_vector_index()
    yield
    reset_vector_index()


def test_effective_type_respects_vector_db_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CHROMA_EPHEMERAL", raising=False)
    monkeypatch.setattr(settings, "vector_db_type", "qdrant")
    assert _effective_vector_db_type() == "qdrant"

    monkeypatch.setattr(settings, "vector_db_type", "chroma")
    assert _effective_vector_db_type() == "chroma"


def test_pytest_env_forces_chroma(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_CHROMA_EPHEMERAL", "1")
    monkeypatch.setattr(settings, "vector_db_type", "qdrant")
    assert _effective_vector_db_type() == "chroma"


def test_get_vector_index_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CHROMA_EPHEMERAL", raising=False)
    monkeypatch.setattr(settings, "vector_db_type", "qdrant")
    index = get_vector_index()
    assert isinstance(index, VectorIndexBridge)
    assert isinstance(index._adapter, QdrantVectorIndex)


def test_get_vector_index_chroma_ephemeral(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_CHROMA_EPHEMERAL", "1")
    index = get_vector_index()
    assert isinstance(index._adapter, EphemeralChromaVectorIndex)


def test_build_memory_indexing_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_CHROMA_EPHEMERAL", "1")
    svc = build_memory_indexing_service(embedding=_FakeEmbedding())
    assert svc._embedding is not None
    assert svc._index is not None
