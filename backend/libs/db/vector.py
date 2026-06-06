"""
向量索引适配器（Qdrant / Chroma）— 纯向量 IO，不含嵌入。

组合根：`domains.agent.infrastructure.memory.vector_store_factory`。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
from typing import Any

import chromadb
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    NearestQuery,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from utils.logging import get_logger

logger = get_logger(__name__)


def _qdrant_collection_vector_size(collection_info: object) -> int | None:
    """从 Qdrant CollectionInfo 解析单向量集合的维度。"""
    try:
        config = collection_info.config  # type: ignore[attr-defined]
        params = config.params  # type: ignore[attr-defined]
        vectors = params.vectors  # type: ignore[attr-defined]
    except AttributeError:
        return None
    if hasattr(vectors, "size"):
        return int(vectors.size)
    if isinstance(vectors, dict):
        for cfg in vectors.values():
            if hasattr(cfg, "size"):
                return int(cfg.size)
    return None


@dataclass(frozen=True)
class VectorHitRecord:
    """向量检索命中（libs 层 DTO，由 factory 桥接为应用层 VectorHit）。"""

    id: str
    score: float
    text: str
    payload: dict[str, Any]


class VectorIndexAdapter(ABC):
    """libs 层向量索引实现基类。"""

    @abstractmethod
    async def ensure_collection(self, name: str, *, dimension: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def upsert_vectors(
        self,
        collection: str,
        *,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search_vectors(
        self,
        collection: str,
        *,
        vector: list[float],
        limit: int = 10,
        query_filter: dict[str, Any] | None = None,
    ) -> list[VectorHitRecord]:
        raise NotImplementedError

    @abstractmethod
    async def delete_vectors(self, collection: str, *, point_ids: list[str]) -> None:
        raise NotImplementedError


class QdrantVectorIndex(VectorIndexAdapter):
    def __init__(self, *, url: str, api_key: str | None = None) -> None:
        self.url = url
        self.api_key = api_key
        self._client: AsyncQdrantClient | None = None

    async def _get_client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(url=self.url, api_key=self.api_key)
        return self._client

    async def ensure_collection(self, name: str, *, dimension: int) -> None:
        client = await self._get_client()
        collections = await client.get_collections()
        if name in [c.name for c in collections.collections]:
            info = await client.get_collection(collection_name=name)
            existing_dim = _qdrant_collection_vector_size(info)
            if existing_dim is None or existing_dim == dimension:
                return
            logger.warning(
                "Qdrant collection %s dimension mismatch (collection=%s, expected=%s); recreating",
                name,
                existing_dim,
                dimension,
            )
            await client.delete_collection(collection_name=name)
        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )
        logger.info("Created collection: %s (dim=%s)", name, dimension)

    async def delete_collection(self, name: str) -> None:
        client = await self._get_client()
        await client.delete_collection(collection_name=name)

    async def upsert_vectors(
        self,
        collection: str,
        *,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        client = await self._get_client()
        await client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    async def search_vectors(
        self,
        collection: str,
        *,
        vector: list[float],
        limit: int = 10,
        query_filter: dict[str, Any] | None = None,
    ) -> list[VectorHitRecord]:
        client = await self._get_client()
        qdrant_filter = None
        if query_filter:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v)) for k, v in query_filter.items()
            ]
            qdrant_filter = Filter(must=conditions)
        results = await client.query_points(
            collection_name=collection,
            query=NearestQuery(nearest=vector),
            limit=limit,
            query_filter=qdrant_filter,
        )
        return [
            VectorHitRecord(
                id=str(r.id),
                score=float(r.score or 0.0),
                text=str((r.payload or {}).get("text", "")),
                payload=dict(r.payload or {}),
            )
            for r in results.points
        ]

    async def delete_vectors(self, collection: str, *, point_ids: list[str]) -> None:
        client = await self._get_client()
        await client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=point_ids),
        )


class ChromaVectorIndex(VectorIndexAdapter):
    def __init__(self, *, persist_directory: str | None = None) -> None:
        self.persist_directory = persist_directory or os.environ.get("CHROMA_PATH", "./chroma_data")
        self._client = None
        self._collections: dict[str, Any] = {}

    def close(self) -> None:
        self._collections.clear()
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(path=self.persist_directory)
        return self._client

    async def ensure_collection(self, name: str, *, dimension: int) -> None:
        client = self._get_client()
        self._collections[name] = client.get_or_create_collection(name=name)
        logger.debug("Ensured collection exists: %s (dimension: %d)", name, dimension)

    async def delete_collection(self, name: str) -> None:
        client = self._get_client()
        client.delete_collection(name=name)
        self._collections.pop(name, None)

    async def upsert_vectors(
        self,
        collection: str,
        *,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        client = self._get_client()
        coll = client.get_or_create_collection(name=collection)
        self._collections[collection] = coll
        text = str(payload.get("text", ""))
        meta = {k: v for k, v in payload.items() if k != "text"} or None
        coll.upsert(
            ids=[point_id],
            documents=[text],
            metadatas=[meta],
            embeddings=[vector],
        )

    async def search_vectors(
        self,
        collection: str,
        *,
        vector: list[float],
        limit: int = 10,
        query_filter: dict[str, Any] | None = None,
    ) -> list[VectorHitRecord]:
        client = self._get_client()
        coll = client.get_or_create_collection(name=collection)
        self._collections[collection] = coll

        chroma_where = None
        if query_filter:

            def _to_chroma_value(val: Any) -> Any:
                if isinstance(val, dict) and any(str(k).startswith("$") for k in val):
                    return val
                return {"$eq": val}

            chroma_where = {k: _to_chroma_value(v) for k, v in query_filter.items()}

        results = coll.query(
            query_embeddings=[vector],
            n_results=limit,
            where=chroma_where,
        )
        hits: list[VectorHitRecord] = []
        if results["ids"] and results["ids"][0]:
            for i, pid in enumerate(results["ids"][0]):
                meta = dict(results["metadatas"][0][i] if results["metadatas"] else {})
                text = results["documents"][0][i] if results["documents"] else ""
                score = 1 - results["distances"][0][i] if results["distances"] else 0.0
                payload = {"text": text, **meta}
                hits.append(
                    VectorHitRecord(
                        id=pid,
                        score=float(score),
                        text=str(text or ""),
                        payload=payload,
                    )
                )
        return hits

    async def delete_vectors(self, collection: str, *, point_ids: list[str]) -> None:
        client = self._get_client()
        try:
            coll = client.get_or_create_collection(name=collection)
            coll.delete(ids=point_ids)
        except Exception:
            logger.warning("Failed to delete vectors from collection=%s ids=%s", collection, point_ids[:5], exc_info=True)


class EphemeralChromaVectorIndex(ChromaVectorIndex):
    def __init__(self) -> None:
        super().__init__(persist_directory="")

    def _get_client(self):
        if self._client is None:
            self._client = chromadb.EphemeralClient()
        return self._client
