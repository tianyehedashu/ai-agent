"""
Memory Service - 记忆服务

实现记忆的存储、检索和管理
"""

import uuid
from typing import Any

from sqlalchemy import select

from db.database import get_session_context
from models.memory import Memory


class MemoryService:
    """记忆服务"""

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
        async with get_session_context() as session:
            memory = Memory(
                user_id=uuid.UUID(user_id),
                type=type,
                content=content,
                importance=importance,
                metadata=metadata or {},
                source_session_id=uuid.UUID(source_session_id) if source_session_id else None,
            )
            session.add(memory)
            await session.flush()
            await session.refresh(memory)
            return memory

    async def get_by_id(self, memory_id: str) -> Memory | None:
        """通过 ID 获取记忆"""
        async with get_session_context() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == uuid.UUID(memory_id))
            )
            return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        type_filter: str | None = None,
    ) -> list[Memory]:
        """获取用户的记忆列表"""
        async with get_session_context() as session:
            query = select(Memory).where(Memory.user_id == uuid.UUID(user_id))

            if type_filter:
                query = query.where(Memory.type == type_filter)

            query = query.order_by(Memory.created_at.desc()).offset(skip).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def delete(self, memory_id: str) -> None:
        """删除记忆"""
        async with get_session_context() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == uuid.UUID(memory_id))
            )
            memory = result.scalar_one_or_none()
            if memory:
                await session.delete(memory)

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 10,
        type_filter: str | None = None,
    ) -> list[Memory]:
        """
        搜索记忆

        TODO: 实现向量搜索
        目前使用简单的文本匹配
        """
        async with get_session_context() as session:
            stmt = (
                select(Memory)
                .where(Memory.user_id == uuid.UUID(user_id))
                .where(Memory.content.ilike(f"%{query}%"))
            )

            if type_filter:
                stmt = stmt.where(Memory.type == type_filter)

            stmt = stmt.order_by(Memory.importance.desc()).limit(top_k)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def import_knowledge(
        self,
        user_id: str,
        content: str,
        source: str,
        chunk_size: int = 1000,
    ) -> str:
        """
        导入知识

        将长文本分块并存储为记忆
        返回任务 ID
        """
        # TODO: 实现异步任务处理
        # 这里简单实现同步版本

        # 分块
        chunks = self._chunk_text(content, chunk_size)

        # 存储
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

        return str(uuid.uuid4())  # 返回任务 ID

    def _chunk_text(self, text: str, chunk_size: int) -> list[str]:
        """分块文本"""
        chunks = []
        words = text.split()
        current_chunk = []
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
