"""
Session Use Case - 会话用例

编排领域服务和仓储，实现会话管理用例。不包含业务逻辑，只负责协调。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.entities.session import SessionDomainService, SessionOwner
from domains.agent.domain.repositories.message_repository import MessageRepository
from domains.agent.domain.repositories.session_repository import SessionRepository
from domains.agent.domain.types import MessageRole
from domains.agent.infrastructure.models.message import Message
from domains.agent.infrastructure.models.session import Session
from domains.agent.infrastructure.repositories import (
    SQLAlchemyMessageRepository,
    SQLAlchemySessionRepository,
)
from exceptions import NotFoundError, PermissionDeniedError
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.agent.domain.services.sandbox_lifecycle import SandboxLifecycleService

logger = get_logger(__name__)


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """安全地将字符串转换为 UUID"""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


class SessionUseCase:
    """会话用例

    协调会话相关的操作，包括 CRUD 和消息管理。使用领域服务进行业务规则验证。
    支持可选注入 SandboxLifecycleService，实现会话与沙箱生命周期联动。
    """

    def __init__(
        self,
        db: AsyncSession,
        session_repo: SessionRepository | None = None,
        message_repo: MessageRepository | None = None,
        sandbox_service: SandboxLifecycleService | None = None,
    ) -> None:
        """初始化会话用例

        Args:
            db: 数据库会话
            session_repo: 会话仓储（可选，默认使用 SQLAlchemy 实现）
            message_repo: 消息仓储（可选，默认使用 SQLAlchemy 实现）
            sandbox_service: 沙箱生命周期服务（可选，用于会话删除时联动清理沙箱）
        """
        self.db = db
        # 支持依赖注入，默认使用 SQLAlchemy 实现
        self.session_repo = session_repo or SQLAlchemySessionRepository(db)
        self.message_repo = message_repo or SQLAlchemyMessageRepository(db)
        self.domain_service = SessionDomainService()
        # 可选的沙箱服务，用于生命周期联动
        self.sandbox_service = sandbox_service

    # =========================================================================
    # Session CRUD
    # =========================================================================

    async def create_session(
        self,
        user_id: str | None = None,
        anonymous_user_id: str | None = None,
        agent_id: str | None = None,
        title: str | None = None,
    ) -> Session:
        """创建会话

        Args:
            user_id: 注册用户 ID
            anonymous_user_id: 匿名用户 ID
            agent_id: 关联Agent ID
            title: 会话标题

        Returns:
            创建的会话对象

        Raises:
            ValueError: 如果参数不符合业务规则时
        """
        # 使用领域服务验证参数
        user_uuid = _safe_uuid(user_id)
        owner = self.domain_service.validate_session_creation(
            user_id=user_uuid,
            anonymous_user_id=anonymous_user_id,
        )

        # 通过仓储创建会话
        session = await self.session_repo.create(
            user_id=owner.user_id,
            anonymous_user_id=owner.anonymous_user_id,
            agent_id=_safe_uuid(agent_id),
            title=title,
        )

        return session

    async def get_session(self, session_id: str) -> Session | None:
        """获取会话"""
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, AttributeError, TypeError):
            return None
        return await self.session_repo.get_by_id(session_uuid)

    async def get_session_or_raise(self, session_id: str) -> Session:
        """获取会话，不存在则抛出异常"""
        session = await self.get_session(session_id)
        if not session:
            raise NotFoundError("Session", session_id)
        return session

    async def list_sessions(
        self,
        user_id: str | None = None,
        anonymous_user_id: str | None = None,
        agent_id: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Session]:
        """获取用户的会话列表"""
        return await self.session_repo.find_by_user(
            user_id=_safe_uuid(user_id),
            anonymous_user_id=anonymous_user_id,
            agent_id=_safe_uuid(agent_id),
            skip=skip,
            limit=limit,
        )

    async def update_session(
        self,
        session_id: str,
        title: str | None | type(...) = ...,  # type: ignore
        status: str | None | type(...) = ...,  # type: ignore
    ) -> Session:
        """更新会话"""
        session = await self.session_repo.update(
            session_id=uuid.UUID(session_id),
            title=title,
            status=status,
        )
        if not session:
            raise NotFoundError("Session", session_id)
        return session

    async def delete_session(self, session_id: str) -> None:
        """删除会话

        如果注入了 SandboxLifecycleService，会联动清理关联的沙箱。

        Args:
            session_id: 会话 ID

        Raises:
            NotFoundError: 会话不存在时
        """
        # 1. 清理关联的沙箱（如果有服务）
        if self.sandbox_service:
            try:
                cleaned = await self.sandbox_service.cleanup_by_session(session_id)
                if cleaned:
                    logger.info("Cleaned up sandbox for session %s", session_id)
            except Exception as e:
                # 沙箱清理失败不应阻止会话删除
                logger.warning(
                    "Failed to cleanup sandbox for session %s: %s",
                    session_id,
                    e,
                )

        # 2. 删除会话
        success = await self.session_repo.delete(uuid.UUID(session_id))
        if not success:
            raise NotFoundError("Session", session_id)

    # =========================================================================
    # Ownership Check
    # =========================================================================

    async def get_session_with_ownership_check(
        self,
        session_id: str,
        owner: SessionOwner,
    ) -> Session:
        """获取会话并验证所有权

        Args:
            session_id: 会话 ID
            owner: 预期的所有者

        Returns:
            会话实体

        Raises:
            NotFoundError: 会话不存在时
            PermissionDeniedError: 所有权验证失败时
        """
        session = await self.get_session_or_raise(session_id)

        if not self.domain_service.check_ownership(session, owner):
            raise PermissionDeniedError(
                message="You don't have permission to access this session",
                resource="Session",
            )

        return session

    # =========================================================================
    # Message Management
    # =========================================================================

    async def get_messages(
        self,
        session_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Message]:
        """获取会话的消息列表"""
        return await self.message_repo.find_by_session(
            session_id=uuid.UUID(session_id),
            skip=skip,
            limit=limit,
        )

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

        同时更新会话的消息计数和 Token 计数。
        """
        # 验证会话存在
        session = await self.get_session(session_id)
        if not session:
            raise NotFoundError("Session", session_id)

        # 支持枚举和字符串
        role_value = role.value if isinstance(role, MessageRole) else role

        # 创建消息
        message = await self.message_repo.create(
            session_id=uuid.UUID(session_id),
            role=role_value,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            metadata=metadata,
            token_count=token_count,
        )

        # 更新会话统计
        await self.session_repo.increment_message_count(
            session_id=uuid.UUID(session_id),
            message_count=1,
            token_count=token_count or 0,
        )

        return message

    async def count_messages(self, session_id: str) -> int:
        """统计会话的消息数量"""
        return await self.message_repo.count_by_session(uuid.UUID(session_id))
