"""将 libs 向量适配器桥接为应用层 VectorIndexPort。"""

# ruff: noqa: TC001 — libs VectorIndexAdapter 仅作构造注入，运行时不需 TYPE_CHECKING 分裂

from __future__ import annotations

from typing import Any

from domains.agent.application.ports.vector_index_port import VectorHit, VectorIndexPort
from libs.db.vector import VectorHitRecord, VectorIndexAdapter


class VectorIndexBridge(VectorIndexPort):
    def __init__(self, adapter: VectorIndexAdapter) -> None:
        self._adapter = adapter

    async def ensure_collection(self, name: str, *, dimension: int) -> None:
        await self._adapter.ensure_collection(name, dimension=dimension)

    async def delete_collection(self, name: str) -> None:
        await self._adapter.delete_collection(name)

    async def upsert_vectors(
        self,
        collection: str,
        *,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        await self._adapter.upsert_vectors(
            collection,
            point_id=point_id,
            vector=vector,
            payload=payload,
        )

    async def search_vectors(
        self,
        collection: str,
        *,
        vector: list[float],
        limit: int = 10,
        query_filter: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        rows = await self._adapter.search_vectors(
            collection,
            vector=vector,
            limit=limit,
            query_filter=query_filter,
        )
        return [_to_vector_hit(r) for r in rows]

    async def delete_vectors(self, collection: str, *, point_ids: list[str]) -> None:
        await self._adapter.delete_vectors(collection, point_ids=point_ids)


def _to_vector_hit(record: VectorHitRecord) -> VectorHit:
    return VectorHit(
        id=record.id,
        score=record.score,
        text=record.text,
        payload=record.payload,
    )
