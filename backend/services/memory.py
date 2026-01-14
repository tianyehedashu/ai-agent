"""
Memory Service - 记忆服务

实现记忆的存储、检索和管理。
"""

from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import NotFoundError
from models.memory import Memory


class MemoryService:
    """记忆服务

    管理用户的长期记忆存储和检索。

    Attributes:
        db: 数据库会话
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
        """创建记忆

        Args:
            user_id: 用户 ID
            type: 记忆类型（fact, preference, procedure 等）
            content: 记忆内容
            importance: 重要性分数（0-1）
            metadata: 元数据（可选）
            source_session_id: 来源会话 ID（可选）

        Returns:
            创建的记忆对象
        """
        memory = Memory(
            user_id=uuid.UUID(user_id),
            type=type,
            content=content,
            importance=importance,
            extra_data=metadata or {},
            source_session_id=uuid.UUID(source_session_id) if source_session_id else None,
        )
        self.db.add(memory)
        await self.db.flush()
        await self.db.refresh(memory)
        return memory

    async def get_by_id(self, memory_id: str) -> Memory | None:
        """通过 ID 获取记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            记忆对象或 None
        """
        result = await self.db.execute(select(Memory).where(Memory.id == uuid.UUID(memory_id)))
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, memory_id: str) -> Memory:
        """通过 ID 获取记忆，不存在则抛出异常

        Args:
            memory_id: 记忆 ID

        Returns:
            记忆对象

        Raises:
            NotFoundError: 记忆不存在时
        """
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
        """获取用户的记忆列表

        Args:
            user_id: 用户 ID
            skip: 跳过记录数
            limit: 返回记录数
            type_filter: 类型筛选（可选）

        Returns:
            记忆列表
        """
        query = select(Memory).where(Memory.user_id == uuid.UUID(user_id))

        if type_filter:
            query = query.where(Memory.type == type_filter)

        query = query.order_by(Memory.created_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete(self, memory_id: str) -> None:
        """删除记忆

        Args:
            memory_id: 记忆 ID

        Raises:
            NotFoundError: 记忆不存在时
        """
        memory = await self.get_by_id_or_raise(memory_id)
        await self.db.delete(memory)

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 10,
        type_filter: str | None = None,
    ) -> list[Memory]:
        """搜索记忆

        使用文本匹配搜索记忆，按重要性排序。

        Args:
            user_id: 用户 ID
            query: 搜索关键词
            top_k: 返回数量
            type_filter: 类型筛选（可选）

        Returns:
            匹配的记忆列表

        Note:
            TODO: 实现向量搜索以提供更好的语义匹配
        """
        stmt = (
            select(Memory)
            .where(Memory.user_id == uuid.UUID(user_id))
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
        """导入知识

        将长文本分块并存储为记忆。

        Args:
            user_id: 用户 ID
            content: 要导入的内容
            source: 内容来源
            chunk_size: 分块大小

        Returns:
            任务 ID

        Note:
            TODO: 实现异步任务处理
        """
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
        """分块文本

        Args:
            text: 原始文本
            chunk_size: 每块最大字符数

        Returns:
            文本块列表
        """
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
