"""
Stats Service - 统计服务

提供系统和用户统计信息。
"""
# pylint: disable=not-callable
# SQLAlchemy 的 func.count 是可调用的，但 Pylint 无法正确识别

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import Agent
from models.message import Message
from models.session import Session
from models.user import User


class StatsService:
    """统计服务

    提供系统级和用户级的统计数据。

    Attributes:
        db: 数据库会话
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_system_stats(self) -> dict[str, Any]:
        """获取系统统计信息

        Returns:
            包含各项统计指标的字典
        """
        # 总用户数
        total_users = await self.db.scalar(select(func.count(User.id)))

        # 总 Agent 数
        total_agents = await self.db.scalar(select(func.count(Agent.id)))

        # 总会话数
        total_sessions = await self.db.scalar(select(func.count(Session.id)))

        # 总消息数
        total_messages = await self.db.scalar(select(func.count(Message.id)))

        # 今日活跃会话数
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
        """获取用户统计信息

        Args:
            user_id: 用户 ID

        Returns:
            包含用户统计指标的字典
        """
        uid = uuid.UUID(user_id)

        # 用户的 Agent 数
        agent_count = await self.db.scalar(select(func.count(Agent.id)).where(Agent.user_id == uid))

        # 用户的会话数
        session_count = await self.db.scalar(
            select(func.count(Session.id)).where(Session.user_id == uid)
        )

        # 用户的消息数
        message_count = await self.db.scalar(
            select(func.count(Message.id))
            .join(Session, Message.session_id == Session.id)
            .where(Session.user_id == uid)
        )

        # 用户的总 Token 数
        total_tokens = await self.db.scalar(
            select(func.sum(Session.token_count)).where(Session.user_id == uid)
        )

        return {
            "agent_count": agent_count or 0,
            "session_count": session_count or 0,
            "message_count": message_count or 0,
            "total_tokens": total_tokens or 0,
        }
