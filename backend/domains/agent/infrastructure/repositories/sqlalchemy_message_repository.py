"""
SQLAlchemy Message Repository - 消息仓储实现

使用 SQLAlchemy 实现消息数据访问。
"""

from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.repositories.message_repository import MessageRepository
from domains.agent.infrastructure.models.message import Message


class SQLAlchemyMessageRepository(MessageRepository):
    """SQLAlchemy 消息仓储实现"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str | None = None,
        tool_calls: dict | None = None,
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        token_count: int | None = None,
    ) -> Message:
        """创建消息"""
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            metadata=metadata or {},
            token_count=token_count,
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def find_by_session(
        self,
        session_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Message]:
        """查询会话的消息列表"""
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_session(self, session_id: uuid.UUID) -> int:
        """统计会话的消息数量"""
        result = await self.db.execute(
            select(func.count(Message.id)).where(Message.session_id == session_id)
        )
        return result.scalar() or 0
