"""
Session Service - 会话服务

提供会话的创建、查询、更新、删除功能。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.types import MessageRole
from exceptions import NotFoundError
from models.message import Message
from models.session import Session


def safe_uuid(value: str | None) -> uuid.UUID | None:
    """安全地将字符串转换为 UUID

    Args:
        value: 要转换的字符串

    Returns:
        UUID 对象或 None（如果值无效）
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


class SessionService:
    """会话服务

    管理用户会话的完整生命周期，包括消息管理。

    Attributes:
        db: 数据库会话
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: str,
        agent_id: str | None = None,
        title: str | None = None,
    ) -> Session:
        """创建会话

        Args:
            user_id: 用户 ID
            agent_id: 关联的 Agent ID（可选）
            title: 会话标题（可选）

        Returns:
            创建的 Session 对象
        """
        user_uuid = safe_uuid(user_id)
        if not user_uuid:
            raise ValueError(f"Invalid user_id format: {user_id}")

        agent_uuid = safe_uuid(agent_id) if agent_id else None

        session = Session(
            user_id=user_uuid,
            agent_id=agent_uuid,
            title=title,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_id(self, session_id: str) -> Session | None:
        """通过 ID 获取会话

        Args:
            session_id: 会话 ID

        Returns:
            Session 对象或 None
        """
        result = await self.db.execute(select(Session).where(Session.id == uuid.UUID(session_id)))
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, session_id: str) -> Session:
        """通过 ID 获取会话，不存在则抛出异常

        Args:
            session_id: 会话 ID

        Returns:
            Session 对象

        Raises:
            NotFoundError: Session 不存在时
        """
        session = await self.get_by_id(session_id)
        if not session:
            raise NotFoundError("Session", session_id)
        return session

    async def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        agent_id: str | None = None,
    ) -> list[Session]:
        """获取用户的会话列表

        Args:
            user_id: 用户 ID
            skip: 跳过记录数
            limit: 返回记录数
            agent_id: 筛选指定 Agent 的会话（可选）

        Returns:
            Session 列表
        """
        # 检查 user_id 是否为有效的 UUID（匿名用户会返回空列表）
        user_uuid = safe_uuid(user_id)
        if not user_uuid:
            return []

        query = select(Session).where(Session.user_id == user_uuid)

        if agent_id:
            agent_uuid = safe_uuid(agent_id)
            if agent_uuid:
                query = query.where(Session.agent_id == agent_uuid)

        query = query.order_by(Session.updated_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        session_id: str,
        title: str | None = None,
        status: str | None = None,
    ) -> Session:
        """更新会话

        Args:
            session_id: 会话 ID
            title: 新标题（可选）
            status: 新状态（可选）

        Returns:
            更新后的 Session

        Raises:
            NotFoundError: Session 不存在时
        """
        session = await self.get_by_id_or_raise(session_id)

        if title is not None:
            session.title = title
        if status is not None:
            session.status = status

        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def delete(self, session_id: str) -> None:
        """删除会话

        Args:
            session_id: 会话 ID

        Raises:
            NotFoundError: Session 不存在时
        """
        session = await self.get_by_id_or_raise(session_id)
        await self.db.delete(session)

    async def get_messages(
        self,
        session_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Message]:
        """获取会话的消息列表

        Args:
            session_id: 会话 ID
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            Message 列表
        """
        result = await self.db.execute(
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
        role: MessageRole | str,
        content: str | None = None,
        tool_calls: dict | None = None,
        tool_call_id: str | None = None,
        metadata: dict | None = None,
        token_count: int | None = None,
    ) -> Message:
        """添加消息

        Args:
            session_id: 会话 ID
            role: 消息角色（使用 MessageRole 枚举或字符串）
            content: 消息内容（可选）
            tool_calls: 工具调用数据（可选）
            tool_call_id: 工具调用 ID（可选）
            metadata: 元数据（可选）
            token_count: Token 数量（可选）

        Returns:
            创建的 Message 对象
        """
        # 支持枚举和字符串
        role_value = role.value if isinstance(role, MessageRole) else role

        message = Message(
            session_id=uuid.UUID(session_id),
            role=role_value,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            metadata=metadata or {},
            token_count=token_count,
        )
        self.db.add(message)

        # 更新会话统计（验证会话存在）
        result = await self.db.execute(select(Session).where(Session.id == uuid.UUID(session_id)))
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("Session", session_id)

        session.message_count += 1
        if token_count:
            session.token_count += token_count

        await self.db.flush()
        await self.db.refresh(message)
        return message
