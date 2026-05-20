"""向量索引应用端口（纯向量 CRUD，不含嵌入）。"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class VectorHit:
    """语义检索命中。"""

    id: str
    score: float
    text: str
    payload: dict[str, Any]

    def as_flat_dict(self) -> dict[str, Any]:
        """兼容旧消费方：id/score/text + payload 字段展平。"""
        return {
            "id": self.id,
            "score": self.score,
            "text": self.text,
            **{k: v for k, v in self.payload.items() if k != "text"},
        }


@runtime_checkable
class VectorIndexPort(Protocol):
    async def ensure_collection(self, name: str, *, dimension: int) -> None: ...

    async def delete_collection(self, name: str) -> None: ...

    async def upsert_vectors(
        self,
        collection: str,
        *,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None: ...

    async def search_vectors(
        self,
        collection: str,
        *,
        vector: list[float],
        limit: int = 10,
        query_filter: dict[str, Any] | None = None,
    ) -> list[VectorHit]: ...

    async def delete_vectors(self, collection: str, *, point_ids: list[str]) -> None: ...
