"""
Stats Service - 统计服务

提供系统和用户统计信息。属于 Runtime 领域的应用服务。
"""

from typing import Any, Protocol
import uuid


class IdentityStatsPort(Protocol):
    async def count_users(self) -> int:
        """统计用户总数"""
        ...


class SessionStatsPort(Protocol):
    async def count_total(self) -> int:
        """统计会话总数"""
        ...

    async def count_active_today(self) -> int:
        """统计今日活跃会话数"""
        ...

    async def count_by_user(self, user_id: str) -> int:
        """统计指定用户的会话数"""
        ...

    async def sum_tokens_by_user(self, user_id: str) -> int:
        """统计指定用户所有会话 token 总量"""
        ...

    async def list_session_ids_by_user(self, user_id: str) -> list[uuid.UUID]:
        """列出指定用户的会话 ID"""
        ...


class AgentStatsRepositoryPort(Protocol):
    async def count_total(self) -> int:
        """统计 Agent 总数"""
        ...

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        """统计指定用户的 Agent 数"""
        ...


class MessageStatsRepositoryPort(Protocol):
    async def count_total(self) -> int:
        """统计消息总数"""
        ...

    async def count_by_session_ids(self, session_ids: list[uuid.UUID]) -> int:
        """统计一组会话下的消息数量"""
        ...


class StatsService:
    """统计服务

    提供系统级和用户级的统计数据。
    """

    def __init__(
        self,
        *,
        identity: IdentityStatsPort,
        sessions: SessionStatsPort,
        agents: AgentStatsRepositoryPort,
        messages: MessageStatsRepositoryPort,
    ) -> None:
        self.identity = identity
        self.sessions = sessions
        self.agents = agents
        self.messages = messages

    async def get_system_stats(self) -> dict[str, Any]:
        """获取系统统计信息"""
        return {
            "total_users": await self.identity.count_users(),
            "total_agents": await self.agents.count_total(),
            "total_sessions": await self.sessions.count_total(),
            "total_messages": await self.messages.count_total(),
            "active_sessions_today": await self.sessions.count_active_today(),
        }

    async def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """获取用户统计信息"""
        uid = uuid.UUID(user_id)
        session_ids = await self.sessions.list_session_ids_by_user(user_id)

        return {
            "agent_count": await self.agents.count_by_user(uid),
            "session_count": await self.sessions.count_by_user(user_id),
            "message_count": await self.messages.count_by_session_ids(session_ids),
            "total_tokens": await self.sessions.sum_tokens_by_user(user_id),
        }
