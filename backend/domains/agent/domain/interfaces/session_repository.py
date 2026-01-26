"""
Session Repository Interface - 会话仓储接口

定义会话数据访问的抽象接口，遵循依赖倒置原则。
Infrastructure 层提供具体实现。
"""

from abc import ABC, abstractmethod
from typing import Protocol
import uuid


class SessionEntity(Protocol):
    """会话实体协议（用于类型检查）"""

    id: uuid.UUID
    user_id: uuid.UUID | None
    anonymous_user_id: str | None
    agent_id: uuid.UUID | None
    title: str | None
    status: str
    message_count: int
    token_count: int


class SessionRepository(ABC):
    """会话仓储接口

    定义会话数据访问的抽象方法。
    具体实现由 Infrastructure 层提供。
    """

    @abstractmethod
    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        agent_id: uuid.UUID | None = None,
        title: str | None = None,
    ) -> SessionEntity:
        """创建会话

        Args:
            user_id: 注册用户 ID
            anonymous_user_id: 匿名用户 ID
            agent_id: 关联的 Agent ID
            title: 会话标题

        Returns:
            创建的会话实体
        """
        ...

    @abstractmethod
    async def get_by_id(self, session_id: uuid.UUID) -> SessionEntity | None:
        """通过 ID 获取会话

        Args:
            session_id: 会话 ID

        Returns:
            会话实体或 None
        """
        ...

    @abstractmethod
    async def find_by_user(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        agent_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[SessionEntity]:
        """查询用户的会话列表

        Args:
            user_id: 注册用户 ID
            anonymous_user_id: 匿名用户 ID
            agent_id: 筛选指定 Agent
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            会话实体列表
        """
        ...

    @abstractmethod
    async def update(
        self,
        session_id: uuid.UUID,
        title: str | None = None,
        status: str | None = None,
    ) -> SessionEntity | None:
        """更新会话

        Args:
            session_id: 会话 ID
            title: 新标题
            status: 新状态

        Returns:
            更新后的会话实体，如果不存在返回 None
        """
        ...

    @abstractmethod
    async def delete(self, session_id: uuid.UUID) -> bool:
        """删除会话

        Args:
            session_id: 会话 ID

        Returns:
            是否删除成功
        """
        ...

    @abstractmethod
    async def increment_message_count(
        self,
        session_id: uuid.UUID,
        message_count: int = 1,
        token_count: int = 0,
    ) -> None:
        """增加消息计数

        Args:
            session_id: 会话 ID
            message_count: 消息增量
            token_count: Token 增量
        """
        ...
