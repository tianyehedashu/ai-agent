"""
Memory Manager - 记忆管理器

负责:
- 记忆提取 (从对话中提取重要信息)
- 记忆存储 (向量数据库 + 关系数据库)
- 记忆更新和删除
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.config import settings
from core.llm.gateway import LLMGateway
from core.memory.retriever import MemoryRetriever
from db.database import get_async_session
from db.vector import VectorStore
from models.memory import Memory
from utils.logging import get_logger

logger = get_logger(__name__)


EXTRACTION_PROMPT = """从以下对话中提取重要的、值得长期记住的信息。

对话内容:
{conversation}

请提取以下类型的信息:
1. 用户偏好 (preferences)
2. 重要事实 (facts)
3. 关键决策 (decisions)
4. 待办事项 (todos)

对于每条记忆，请给出:
- content: 记忆内容
- type: 记忆类型 (preference/fact/decision/todo)
- importance: 重要性评分 (1-10)

以 JSON 数组格式返回，如果没有值得记住的信息，返回空数组 []。
"""


class MemoryManager:
    """
    记忆管理器

    负责记忆的完整生命周期管理
    """

    def __init__(
        self,
        llm: LLMGateway | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.llm = llm or LLMGateway()
        self.vector_store = vector_store
        self.retriever = MemoryRetriever(vector_store)

    async def extract_memories(
        self,
        session_id: str,
        user_id: str,
        conversation: list[dict[str, Any]],
    ) -> list[Memory]:
        """
        从对话中提取记忆

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            conversation: 对话历史

        Returns:
            提取的记忆列表
        """
        # 格式化对话
        conv_text = self._format_conversation(conversation)

        # 调用 LLM 提取记忆
        prompt = EXTRACTION_PROMPT.format(conversation=conv_text)

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=settings.default_model,
                temperature=0.3,
            )

            # 解析响应
            content = response.content or "[]"
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            extracted = json.loads(content.strip())

            if not isinstance(extracted, list):
                return []

            # 创建记忆对象
            memories = []
            for item in extracted:
                if not isinstance(item, dict):
                    continue

                memory = await self.create(
                    user_id=user_id,
                    content=item.get("content", ""),
                    memory_type=item.get("type", "fact"),
                    importance=float(item.get("importance", 5)),
                    source_session_id=session_id,
                    metadata={"extracted": True},
                )
                memories.append(memory)

            logger.info("Extracted %d memories from session %s", len(memories), session_id)
            return memories

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Memory extraction error: %s", e, exc_info=True)
            return []

    async def create(
        self,
        user_id: str,
        content: str,
        memory_type: str = "fact",
        importance: float = 5.0,
        source_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        """
        创建记忆

        Args:
            user_id: 用户 ID
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性 (1-10)
            source_session_id: 来源会话 ID
            metadata: 元数据

        Returns:
            创建的记忆
        """
        memory_id = uuid.uuid4()

        async with get_async_session() as session:
            memory = Memory(
                id=memory_id,
                user_id=uuid.UUID(user_id),
                content=content,
                type=memory_type,
                importance=float(importance),
                source_session_id=uuid.UUID(source_session_id) if source_session_id else None,
                metadata=metadata or {},
            )

            session.add(memory)
            await session.commit()
            await session.refresh(memory)

        # 存储向量
        if self.vector_store:
            await self.vector_store.upsert(
                collection="memories",
                point_id=str(memory_id),
                text=content,
                metadata={
                    "user_id": user_id,
                    "memory_type": memory_type,
                    "importance": importance,
                },
            )

        return memory

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        importance: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory | None:
        """更新记忆"""
        async with get_async_session() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == uuid.UUID(memory_id))
            )
            memory = result.scalar_one_or_none()

            if not memory:
                return None

            if content is not None:
                memory.content = content
            if importance is not None:
                memory.importance = float(importance)
            if metadata is not None:
                memory.metadata = {**memory.metadata, **metadata}

            memory.updated_at = datetime.now(timezone.utc)
            memory.access_count += 1

            await session.commit()
            await session.refresh(memory)

            # 更新向量
            if self.vector_store and content:
                await self.vector_store.upsert(
                    collection="memories",
                    point_id=str(memory_id),
                    text=content,
                    metadata={
                        "user_id": str(memory.user_id),
                        "memory_type": memory.type,
                        "importance": memory.importance,
                    },
                )

            return memory

    async def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        async with get_async_session() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == uuid.UUID(memory_id))
            )
            memory = result.scalar_one_or_none()

            if not memory:
                return False

            await session.delete(memory)
            await session.commit()

            # 删除向量
            if self.vector_store:
                await self.vector_store.delete(
                    collection="memories",
                    point_ids=[memory_id],
                )

            return True

    async def get(self, memory_id: str) -> Memory | None:
        """获取记忆"""
        async with get_async_session() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == uuid.UUID(memory_id))
            )
            return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        """列出用户的记忆"""
        async with get_async_session() as session:
            query = select(Memory).where(Memory.user_id == uuid.UUID(user_id))

            if memory_type:
                query = query.where(Memory.type == memory_type)

            query = query.order_by(Memory.importance.desc(), Memory.updated_at.desc())
            query = query.limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[Memory]:
        """搜索记忆"""
        return await self.retriever.retrieve(
            user_id=user_id,
            query=query,
            limit=limit,
        )

    def _format_conversation(self, conversation: list[dict[str, Any]]) -> str:
        """格式化对话"""
        lines = []
        for msg in conversation:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
