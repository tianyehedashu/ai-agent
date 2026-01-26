"""
Message Repository Interface - 消息仓储接口

定义消息数据访问的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol
import uuid


class MessageEntity(Protocol):
    """消息实体协议（用于类型检查）"""

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str | None
    tool_calls: dict | None
    tool_call_id: str | None
    metadata: dict
    token_count: int | None


class MessageRepository(ABC):
    """消息仓储接口"""

    @abstractmethod
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
        """创建消息

        Args:
            session_id: 会话 ID
            role: 消息角色
            content: 消息内容
            tool_calls: 工具调用数据
            tool_call_id: 工具调用 ID
            metadata: 元数据
            token_count: Token 数量

        Returns:
            创建的消息实体
        """
        ...

    @abstractmethod
    async def find_by_session(
        self,
        session_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[MessageEntity]:
        """查询会话的消息列表

        Args:
            session_id: 会话 ID
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            消息实体列表（按时间升序）
        """
        ...

    @abstractmethod
    async def count_by_session(self, session_id: uuid.UUID) -> int:
        """统计会话的消息数量

        Args:
            session_id: 会话 ID

        Returns:
            消息数量
        """
        ...
