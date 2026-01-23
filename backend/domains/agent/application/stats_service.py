"""
Stats Service - 统计服务

提供系统和用户统计信息。属于 Runtime 领域的应用服务。
"""
# pylint: disable=not-callable

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.agent import Agent
from domains.agent.infrastructure.models.message import Message
from domains.agent.infrastructure.models.session import Session
from domains.identity.infrastructure.models.user import User


class StatsService:
    """统计服务

    提供系统级和用户级的统计数据。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_system_stats(self) -> dict[str, Any]:
        """获取系统统计信息"""
        total_users = await self.db.scalar(select(func.count(User.id)))
        total_agents = await self.db.scalar(select(func.count(Agent.id)))
        total_sessions = await self.db.scalar(select(func.count(Session.id)))
        total_messages = await self.db.scalar(select(func.count(Message.id)))

        today = datetime.now(UTC).date()
        active_sessions_today = await self.db.scalar(
            select(func.count(Session.id)).where(func.date(Session.updated_at) == today)
        )

        return {
            "total_users": total_users or 0,
            "total_agents": total_agents or 0,
            "total_sessions": total_sessions or 0,
            "total_messages": total_messages or 0,
            "active_sessions_today": active_sessions_today or 0,
        }

    async def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """获取用户统计信息"""
        uid = uuid.UUID(user_id)

        agent_count = await self.db.scalar(select(func.count(Agent.id)).where(Agent.user_id == uid))
        session_count = await self.db.scalar(
            select(func.count(Session.id)).where(Session.user_id == uid)
        )
        message_count = await self.db.scalar(
            select(func.count(Message.id))
            .join(Session, Message.session_id == Session.id)
            .where(Session.user_id == uid)
        )
        total_tokens = await self.db.scalar(
            select(func.sum(Session.token_count)).where(Session.user_id == uid)
        )

        return {
            "agent_count": agent_count or 0,
            "session_count": session_count or 0,
            "message_count": message_count or 0,
            "total_tokens": total_tokens or 0,
        }
