"""Message application port (provider: agent domain)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import uuid

    from domains.agent.domain.interfaces.message_repository import MessageEntity


class MessageApplicationPort(Protocol):
    """Session 等域通过此端口读写消息，不直接依赖 agent infrastructure。"""

    async def create(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str | None = None,
        tool_calls: dict | None = None,
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        token_count: int | None = None,
    ) -> MessageEntity:
        """创建消息"""
        ...

    async def find_by_session(
        self,
        session_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[MessageEntity]:
        """查询会话消息列表"""
        ...

    async def count_by_session(self, session_id: uuid.UUID) -> int:
        """统计会话消息数"""
        ...


__all__ = ["MessageApplicationPort"]
