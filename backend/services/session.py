"""
Session Service - 会话服务
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.database import get_session_context
from models.message import Message
from models.session import Session


class SessionService:
    """会话服务"""

    async def create(
        self,
        user_id: str,
        agent_id: str | None = None,
        title: str | None = None,
    ) -> Session:
        """创建会话"""
        async with get_session_context() as db_session:
            session = Session(
                user_id=uuid.UUID(user_id),
                agent_id=uuid.UUID(agent_id) if agent_id else None,
                title=title,
            )
            db_session.add(session)
            await db_session.flush()
            await db_session.refresh(session)
            return session

    async def get_by_id(self, session_id: str) -> Session | None:
        """通过 ID 获取会话"""
        async with get_session_context() as db_session:
            result = await db_session.execute(
                select(Session).where(Session.id == uuid.UUID(session_id))
            )
            return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        agent_id: str | None = None,
    ) -> list[Session]:
        """获取用户的会话列表"""
        async with get_session_context() as db_session:
            query = select(Session).where(Session.user_id == uuid.UUID(user_id))

            if agent_id:
                query = query.where(Session.agent_id == uuid.UUID(agent_id))

            query = query.order_by(Session.updated_at.desc()).offset(skip).limit(limit)

            result = await db_session.execute(query)
            return list(result.scalars().all())

    async def update(self, session_id: str, data: dict[str, Any]) -> Session:
        """更新会话"""
        async with get_session_context() as db_session:
            result = await db_session.execute(
                select(Session).where(Session.id == uuid.UUID(session_id))
            )
            session = result.scalar_one_or_none()
            if not session:
                raise ValueError("Session not found")

            for key, value in data.items():
                if hasattr(session, key):
                    setattr(session, key, value)

            await db_session.flush()
            await db_session.refresh(session)
            return session

    async def delete(self, session_id: str) -> None:
        """删除会话"""
        async with get_session_context() as db_session:
            result = await db_session.execute(
                select(Session).where(Session.id == uuid.UUID(session_id))
            )
            session = result.scalar_one_or_none()
            if session:
                await db_session.delete(session)

    async def get_messages(
        self,
        session_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Message]:
        """获取会话的消息列表"""
        async with get_session_context() as db_session:
            result = await db_session.execute(
                select(Message)
                .where(Message.session_id == uuid.UUID(session_id))
                .order_by(Message.created_at.asc())
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str | None = None,
        tool_calls: dict | None = None,
        tool_call_id: str | None = None,
        metadata: dict | None = None,
        token_count: int | None = None,
    ) -> Message:
        """添加消息"""
        async with get_session_context() as db_session:
            message = Message(
                session_id=uuid.UUID(session_id),
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                metadata=metadata or {},
                token_count=token_count,
            )
            db_session.add(message)

            # 更新会话统计
            result = await db_session.execute(
                select(Session).where(Session.id == uuid.UUID(session_id))
            )
            session = result.scalar_one_or_none()
            if session:
                session.message_count += 1
                if token_count:
                    session.token_count += token_count

            await db_session.flush()
            await db_session.refresh(message)
            return message
