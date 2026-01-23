"""
SQLAlchemy Session Repository - 会话仓储实现

使用 SQLAlchemy 实现会话数据访问。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.repositories.session_repository import SessionRepository
from domains.agent.infrastructure.models.session import Session


class SQLAlchemySessionRepository(SessionRepository):
    """SQLAlchemy 会话仓储实现"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        agent_id: uuid.UUID | None = None,
        title: str | None = None,
    ) -> Session:
        """创建会话"""
        session = Session(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            agent_id=agent_id,
            title=title,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        """通过 ID 获取会话"""
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def find_by_user(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        agent_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Session]:
        """查询用户的会话列表"""
        # 构建查询条件
        if user_id:
            query = select(Session).where(Session.user_id == user_id)
        elif anonymous_user_id:
            query = select(Session).where(Session.anonymous_user_id == anonymous_user_id)
        else:
            return []

        if agent_id:
            query = query.where(Session.agent_id == agent_id)

        query = query.order_by(Session.updated_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        session_id: uuid.UUID,
        title: str | None = ...,
        status: str | None = ...,
    ) -> Session | None:
        """更新会话

        Args:
            title: 如果为 ...，则不更新；如果为 None，则清除标题；如果为字符串，则设置标题
            status: 如果为 ...，则不更新；如果为 None，则清除状态；如果为字符串，则设置状态
        """
        session = await self.get_by_id(session_id)
        if not session:
            return None

        if title is not ...:
            session.title = title
        if status is not ...:
            session.status = status

        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def delete(self, session_id: uuid.UUID) -> bool:
        """删除会话"""
        session = await self.get_by_id(session_id)
        if not session:
            return False

        await self.db.delete(session)
        return True

    async def increment_message_count(
        self,
        session_id: uuid.UUID,
        message_count: int = 1,
        token_count: int = 0,
    ) -> None:
        """增加消息计数"""
        session = await self.get_by_id(session_id)
        if session:
            session.message_count += message_count
            if token_count:
                session.token_count += token_count
            await self.db.flush()
