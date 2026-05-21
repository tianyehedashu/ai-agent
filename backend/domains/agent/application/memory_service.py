"""
Memory Service - 记忆服务

实现记忆的存储、检索和管理。属于 Runtime 领域的应用服务。
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.memory import Memory
from domains.agent.infrastructure.repositories.memory_repository import MemoryRepository
class MemoryService:
    """记忆服务（委托 ``MemoryRepository``，写入带 ``tenant_id``）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = MemoryRepository(db)

    async def create(
        self,
        user_id: str,
        type: str,
        content: str,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        source_session_id: str | None = None,
    ) -> Memory:
        return await self._repo.create(
            user_id=user_id,
            type=type,
            content=content,
            importance=importance,
            metadata=metadata,
            source_session_id=source_session_id,
        )

    async def get_by_id(self, memory_id: str) -> Memory | None:
        return await self._repo.get_by_id(memory_id)

    async def get_by_id_or_raise(self, memory_id: str) -> Memory:
        return await self._repo.get_by_id_or_raise(memory_id)

    async def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        type_filter: str | None = None,
    ) -> list[Memory]:
        return await self._repo.list_by_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            type_filter=type_filter,
        )

    async def delete(self, memory_id: str) -> None:
        await self._repo.delete(memory_id)

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 10,
        type_filter: str | None = None,
    ) -> list[Memory]:
        return await self._repo.search(
            user_id=user_id,
            query=query,
            top_k=top_k,
            type_filter=type_filter,
        )

    async def import_knowledge(
        self,
        user_id: str,
        content: str,
        source: str,
        chunk_size: int = 1000,
    ) -> str:
        return await self._repo.import_knowledge(
            user_id=user_id,
            content=content,
            source=source,
            chunk_size=chunk_size,
        )

    def _chunk_text(self, text: str, chunk_size: int) -> list[str]:
        return self._repo._chunk_text(text, chunk_size)
