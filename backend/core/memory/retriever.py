"""
Memory Retriever - 记忆检索器

实现多路召回策略:
- 向量相似度召回
- 关键词召回
- 时间衰减
- 重要性加权
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_async_session
from db.vector import VectorStore
from models.memory import Memory
from utils.logging import get_logger

logger = get_logger(__name__)


class MemoryRetriever:
    """
    记忆检索器

    使用多路召回策略检索相关记忆
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        time_decay_days: int = 30,
        importance_weight: float = 0.3,
        recency_weight: float = 0.2,
        relevance_weight: float = 0.5,
    ) -> None:
        self.vector_store = vector_store
        self.time_decay_days = time_decay_days
        self.importance_weight = importance_weight
        self.recency_weight = recency_weight
        self.relevance_weight = relevance_weight

    async def retrieve(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        memory_types: list[str] | None = None,
        min_importance: int = 1,
    ) -> list[Memory]:
        """
        检索相关记忆

        Args:
            user_id: 用户 ID
            query: 查询文本
            limit: 返回数量
            memory_types: 过滤的记忆类型
            min_importance: 最小重要性

        Returns:
            相关记忆列表
        """
        candidates: list[tuple[Memory, float]] = []

        # 1. 向量召回
        if self.vector_store:
            vector_results = await self._vector_recall(
                user_id=user_id,
                query=query,
                limit=limit * 2,
            )
            for memory, score in vector_results:
                candidates.append((memory, score * self.relevance_weight))

        # 2. 关键词召回
        keyword_results = await self._keyword_recall(
            user_id=user_id,
            query=query,
            limit=limit * 2,
        )
        for memory in keyword_results:
            # 检查是否已在候选中
            existing = next((c for c in candidates if c[0].id == memory.id), None)
            if existing:
                # 增加分数
                idx = candidates.index(existing)
                candidates[idx] = (existing[0], existing[1] + 0.3)
            else:
                candidates.append((memory, 0.3))

        # 3. 计算最终分数
        scored_memories = []
        now = datetime.utcnow()

        for memory, base_score in candidates:
            # 过滤条件
            if memory_types and memory.memory_type not in memory_types:
                continue
            if memory.importance < min_importance:
                continue

            # 重要性分数 (归一化到 0-1)
            importance_score = memory.importance / 10.0

            # 时间衰减分数
            days_old = (now - memory.updated_at).days
            recency_score = max(0, 1 - days_old / self.time_decay_days)

            # 综合分数
            final_score = (
                base_score
                + importance_score * self.importance_weight
                + recency_score * self.recency_weight
            )

            scored_memories.append((memory, final_score))

        # 排序并返回
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in scored_memories[:limit]]

    async def _vector_recall(
        self,
        user_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[Memory, float]]:
        """向量召回"""
        if not self.vector_store:
            return []

        try:
            results = await self.vector_store.search(
                collection="memories",
                query=query,
                limit=limit,
                filter={"user_id": user_id},
            )

            memories = []
            async with get_async_session() as session:
                for result in results:
                    memory_id = result.get("id")
                    score = result.get("score", 0)

                    if memory_id:
                        db_result = await session.execute(
                            select(Memory).where(Memory.id == uuid.UUID(memory_id))
                        )
                        memory = db_result.scalar_one_or_none()
                        if memory:
                            memories.append((memory, score))

            return memories

        except Exception as e:
            logger.error(f"Vector recall error: {e}")
            return []

    async def _keyword_recall(
        self,
        user_id: str,
        query: str,
        limit: int,
    ) -> list[Memory]:
        """关键词召回"""
        # 提取关键词 (简单的分词)
        keywords = query.lower().split()

        async with get_async_session() as session:
            # 构建 LIKE 条件
            conditions = [
                Memory.content.ilike(f"%{kw}%")
                for kw in keywords[:5]  # 限制关键词数量
            ]

            query_stmt = (
                select(Memory)
                .where(Memory.user_id == uuid.UUID(user_id))
                .where(or_(*conditions) if conditions else True)
                .order_by(Memory.importance.desc())
                .limit(limit)
            )

            result = await session.execute(query_stmt)
            return list(result.scalars().all())

    async def get_context_memories(
        self,
        user_id: str,
        context: str,
        limit: int = 5,
    ) -> list[Memory]:
        """
        获取上下文相关的记忆

        用于在对话开始时注入相关记忆
        """
        return await self.retrieve(
            user_id=user_id,
            query=context,
            limit=limit,
            min_importance=3,
        )

    async def get_recent_memories(
        self,
        user_id: str,
        days: int = 7,
        limit: int = 10,
    ) -> list[Memory]:
        """获取最近的记忆"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with get_async_session() as session:
            result = await session.execute(
                select(Memory)
                .where(
                    and_(
                        Memory.user_id == uuid.UUID(user_id),
                        Memory.updated_at >= cutoff,
                    )
                )
                .order_by(Memory.updated_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_important_memories(
        self,
        user_id: str,
        min_importance: int = 7,
        limit: int = 10,
    ) -> list[Memory]:
        """获取重要记忆"""
        async with get_async_session() as session:
            result = await session.execute(
                select(Memory)
                .where(
                    and_(
                        Memory.user_id == uuid.UUID(user_id),
                        Memory.importance >= min_importance,
                    )
                )
                .order_by(Memory.importance.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
