"""Message application service — implements MessageApplicationPort."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from domains.agent.infrastructure.repositories.message_repository import MessageRepository

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.agent.domain.interfaces.message_repository import MessageEntity


class MessageUseCase:
    """消息应用服务（Agent 域对外端口实现）。"""

    def __init__(
        self,
        db: AsyncSession,
        *,
        message_repo: MessageRepository | None = None,
    ) -> None:
        self._repo = message_repo or MessageRepository(db)

    async def create(
        self,
        session_id: UUID,
        role: str,
        content: str | None = None,
        tool_calls: dict | None = None,
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        token_count: int | None = None,
    ) -> MessageEntity:
        return await self._repo.create(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            metadata=metadata,
            token_count=token_count,
        )

    async def find_by_session(
        self,
        session_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[MessageEntity]:
        return await self._repo.find_by_session(
            session_id=session_id,
            skip=skip,
            limit=limit,
        )

    async def count_by_session(self, session_id: UUID) -> int:
        return await self._repo.count_by_session(session_id)


__all__ = ["MessageUseCase"]
