"""
Session Repository - 会话仓储实现

实现会话数据访问，支持自动权限过滤。
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.interfaces.session_repository import (
    SessionRepository as SessionRepositoryInterface,
)
from domains.agent.infrastructure.models.session import Session
from libs.db.base_repository import OwnedRepositoryBase
from libs.db.permission_context import get_permission_context


class SessionRepository(OwnedRepositoryBase[Session], SessionRepositoryInterface):
    """会话仓储实现

    继承 OwnedRepositoryBase 提供自动权限过滤功能。
    支持注册用户和匿名用户。
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.db = db

    @property
    def model_class(self) -> type[Session]:
        """返回模型类"""
        return Session

    @property
    def anonymous_user_id_column(self) -> str:
        """匿名用户 ID 字段名"""
        return "anonymous_user_id"

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
        """通过 ID 获取会话（自动检查所有权）"""
        return await self.get_owned(session_id)

    async def find_by_user(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        agent_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Session]:
        """查询用户的会话列表（自动过滤当前用户的数据）

        Args:
            user_id: 注册用户 ID（如果提供，必须与 PermissionContext 一致）
            anonymous_user_id: 匿名用户 ID（如果提供，必须与 PermissionContext 一致）
            agent_id: 筛选指定 Agent
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            会话实体列表

        Raises:
            ValueError: 如果传递的 user_id 或 anonymous_user_id 与 PermissionContext 不一致
        """
        # 验证传递的参数与 PermissionContext 一致（防止授权漏洞）
        # 管理员可以查询任何用户的数据，所以跳过验证
        ctx = get_permission_context()
        if ctx and not ctx.is_admin:
            # 如果传递了 user_id，必须与上下文一致
            if user_id is not None and ctx.user_id != user_id:
                raise ValueError(
                    f"user_id parameter ({user_id}) does not match PermissionContext ({ctx.user_id}). "
                    "This may indicate an authorization bug."
                )
            # 如果传递了 anonymous_user_id，必须与上下文一致
            if anonymous_user_id is not None and ctx.anonymous_user_id != anonymous_user_id:
                raise ValueError(
                    f"anonymous_user_id parameter ({anonymous_user_id}) does not match PermissionContext ({ctx.anonymous_user_id}). "
                    "This may indicate an authorization bug."
                )

        # 使用 find_owned 自动应用权限过滤
        return await self.find_owned(
            skip=skip,
            limit=limit,
            order_by="updated_at",
            order_desc=True,
            agent_id=agent_id,
        )

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
