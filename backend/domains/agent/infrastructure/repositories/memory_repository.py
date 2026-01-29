"""
Memory Repository - 记忆仓储

实现记忆的持久化操作。属于基础设施层。
"""

from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.memory import Memory
from exceptions import NotFoundError


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """安全地将字符串转换为 UUID"""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


class MemoryRepository:
    """记忆仓储

    管理用户的长期记忆存储和检索。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: str,
        type: str,
        content: str,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        source_session_id: str | None = None,
    ) -> Memory:
        """创建记忆"""
        user_uuid = _safe_uuid(user_id)
        if not user_uuid:
            raise ValueError(f"Invalid user_id format: {user_id}")

        memory = Memory(
            user_id=user_uuid,
            type=type,
            content=content,
            importance=importance,
            extra_data=metadata or {},
            source_session_id=_safe_uuid(source_session_id),
        )
        self.db.add(memory)
        await self.db.flush()
        await self.db.refresh(memory)
        return memory

    async def get_by_id(self, memory_id: str) -> Memory | None:
        """通过 ID 获取记忆"""
        result = await self.db.execute(select(Memory).where(Memory.id == uuid.UUID(memory_id)))
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, memory_id: str) -> Memory:
        """通过 ID 获取记忆，不存在则抛出异常"""
        memory = await self.get_by_id(memory_id)
        if not memory:
            raise NotFoundError("Memory", memory_id)
        return memory

    async def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        type_filter: str | None = None,
    ) -> list[Memory]:
        """获取用户的记忆列表"""
        user_uuid = _safe_uuid(user_id)
        if not user_uuid:
            return []

        query = select(Memory).where(Memory.user_id == user_uuid)

        if type_filter:
            query = query.where(Memory.type == type_filter)

        query = query.order_by(Memory.created_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete(self, memory_id: str) -> None:
        """删除记忆"""
        memory = await self.get_by_id_or_raise(memory_id)
        await self.db.delete(memory)

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 10,
        type_filter: str | None = None,
    ) -> list[Memory]:
        """搜索记忆"""
        user_uuid = _safe_uuid(user_id)
        if not user_uuid:
            return []

        stmt = (
            select(Memory)
            .where(Memory.user_id == user_uuid)
            .where(Memory.content.ilike(f"%{query}%"))
        )

        if type_filter:
            stmt = stmt.where(Memory.type == type_filter)

        stmt = stmt.order_by(Memory.importance.desc()).limit(top_k)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def import_knowledge(
        self,
        user_id: str,
        content: str,
        source: str,
        chunk_size: int = 1000,
    ) -> str:
        """导入知识"""
        chunks = self._chunk_text(content, chunk_size)

        for i, chunk in enumerate(chunks):
            await self.create(
                user_id=user_id,
                type="fact",
                content=chunk,
                importance=0.5,
                metadata={
                    "source": source,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            )

        return str(uuid.uuid4())

    def _chunk_text(self, text: str, chunk_size: int) -> list[str]:
        """分块文本"""
        chunks = []
        words = text.split()
        current_chunk: list[str] = []
        current_size = 0

        for word in words:
            word_size = len(word) + 1
            if current_size + word_size > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks
