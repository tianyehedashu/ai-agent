"""
Stats Service - 统计服务
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from db.database import get_session_context
from models.agent import Agent
from models.message import Message
from models.session import Session
from models.user import User


class StatsService:
    """统计服务"""

    async def get_system_stats(self) -> dict[str, Any]:
        """获取系统统计信息"""
        async with get_session_context() as session:
            # 总用户数
            total_users = await session.scalar(select(func.count(User.id)))

            # 总 Agent 数
            total_agents = await session.scalar(select(func.count(Agent.id)))

            # 总会话数
            total_sessions = await session.scalar(select(func.count(Session.id)))

            # 总消息数
            total_messages = await session.scalar(select(func.count(Message.id)))

            # 今日活跃会话数
            today = datetime.utcnow().date()
            active_sessions_today = await session.scalar(
                select(func.count(Session.id)).where(
                    func.date(Session.updated_at) == today
                )
            )

            return {
                "total_users": total_users or 0,
                "total_agents": total_agents or 0,
                "total_sessions": total_sessions or 0,
                "total_messages": total_messages or 0,
                "active_sessions_today": active_sessions_today or 0,
            }
