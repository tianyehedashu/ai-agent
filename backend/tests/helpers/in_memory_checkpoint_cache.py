"""集成/单测用：不依赖 Redis 的检查点缓存存根。"""

from __future__ import annotations

from typing import Any


class InMemoryCheckpointCache:
    """实现 ``CheckpointCache`` 所用方法的最小子集。"""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._session_ids: dict[str, str] = {}

    async def save_checkpoint(
        self,
        checkpoint_id: str,
        data: dict[str, Any],
        ttl: int = 86400 * 7,
    ) -> None:
        del ttl
        self._data[checkpoint_id] = data

    async def bind_checkpoint_session(
        self,
        checkpoint_id: str,
        session_id: str,
        *,
        ttl: int = 86400 * 7,
    ) -> None:
        del ttl
        self._session_ids[checkpoint_id] = session_id

    async def resolve_session_id(self, checkpoint_id: str) -> str | None:
        if checkpoint_id in self._session_ids:
            return self._session_ids[checkpoint_id]
        data = self._data.get(checkpoint_id)
        if data is None:
            return None
        raw = data.get("session_id")
        return raw if isinstance(raw, str) else None

    async def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        return self._data.get(checkpoint_id)

    async def add_to_session_index(
        self,
        session_id: str,
        checkpoint_id: str,
        step: int,
    ) -> None:
        del session_id, checkpoint_id, step
