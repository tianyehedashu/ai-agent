"""
Session Use Case - 会话用例

编排领域服务和仓储，实现会话管理用例。不包含业务逻辑，只负责协调。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from domains.agent.domain.types import MessageRole
from domains.identity.domain.anonymous_tenant import resolve_anonymous_tenant_id
from domains.identity.domain.rbac import Role
from domains.identity.domain.types import Principal
from domains.session.domain.entities.session import SessionDomainService, SessionOwner
from domains.session.domain.policies.session_access import can_access_personal_session
from domains.session.infrastructure.repositories import SessionRepository
from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner
from libs.exceptions import NotFoundError, PermissionDeniedError
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.agent.application.ports.message_port import MessageApplicationPort
    from domains.agent.domain.interfaces.message_repository import MessageEntity
    from domains.agent.domain.services.sandbox_lifecycle import SandboxLifecycleService
    from domains.session.domain.interfaces.session_repository import (
        SessionRepository as SessionRepositoryInterface,
    )
    from domains.session.infrastructure.models.session import Session

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
        session_repo: SessionRepositoryInterface | None = None,
        message_service: MessageApplicationPort | None = None,
        sandbox_service: SandboxLifecycleService | None = None,
    ) -> None:
        """初始化会话用例

        Args:
            db: 数据库会话
            session_repo: 会话仓储（可选，默认使用默认实现）
            message_service: 消息应用端口（须由组合根注入，禁止默认实例化 agent infrastructure）
            sandbox_service: 沙箱生命周期服务（可选，用于会话删除时联动清理沙箱）
        """
        if message_service is None:
            raise ValueError("message_service is required; inject MessageUseCase from composition root")
        self.db = db
        self.session_repo = session_repo or SessionRepository(db)
        self.message_service = message_service
        self.domain_service = SessionDomainService()
        # 可选的沙箱服务，用于生命周期联动
        self.sandbox_service = sandbox_service

    async def _tenant_id_for_owner(self, owner: SessionOwner) -> uuid.UUID:
        if owner.user_id is not None:
            return await PersonalTeamProvisioner(self.db).ensure_personal_team(owner.user_id)
        if owner.anonymous_user_id:
            return resolve_anonymous_tenant_id(owner.anonymous_user_id)
        raise ValueError("SessionOwner must have user_id or anonymous_user_id")

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

    async def list_sessions_for_principal(
        self,
        *,
        principal_id: str,
        is_anonymous: bool,
        agent_id: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Session]:
        """按认证主体列出 personal 工作区会话。"""
        owner = SessionOwner.from_principal_id(principal_id, is_anonymous)
        return await self.list_sessions(
            user_id=str(owner.user_id) if owner.user_id else None,
            anonymous_user_id=owner.anonymous_user_id,
            agent_id=agent_id,
            skip=skip,
            limit=limit,
        )

    async def create_session_for_principal(
        self,
        *,
        principal_id: str,
        is_anonymous: bool,
        agent_id: str | None = None,
        title: str | None = None,
    ) -> Session:
        """按认证主体创建会话。"""
        owner = SessionOwner.from_principal_id(principal_id, is_anonymous)
        return await self.create_session(
            user_id=str(owner.user_id) if owner.user_id else None,
            anonymous_user_id=owner.anonymous_user_id,
            agent_id=agent_id,
            title=title,
        )

    async def update_session(
        self,
        session_id: str,
        title: str | None | type(...) = ...,  # type: ignore
        status: str | None | type(...) = ...,  # type: ignore
        gateway_verbose_request_log: bool | None | type(...) = ...,  # type: ignore
        creative_mode: str | None | type(...) = ...,  # type: ignore
        image_gen_model_ref: str | None | type(...) = ...,  # type: ignore
        video_model_ref: str | None | type(...) = ...,  # type: ignore
    ) -> Session:
        """更新会话"""
        sid = uuid.UUID(session_id)
        cfg_slice: dict[str, Any] = {}
        if gateway_verbose_request_log is not ...:
            cfg_slice["gateway_verbose_request_log"] = bool(gateway_verbose_request_log)
        if creative_mode is not ...:
            cfg_slice["creative_mode"] = creative_mode
        if image_gen_model_ref is not ...:
            cfg_slice["image_gen_model_ref"] = image_gen_model_ref
        if video_model_ref is not ...:
            cfg_slice["video_model_ref"] = video_model_ref
        if cfg_slice:
            await self.session_repo.update_config(sid, cfg_slice)
        session = await self.session_repo.update(
            session_id=sid,
            title=title,
            status=status,
        )
        if not session:
            raise NotFoundError("Session", session_id)
        return session

    def get_session_mcp_config(self, session: Session) -> dict:
        """从会话实体读取 MCP 配置（enabled_servers）。

        调用方需已校验会话存在与所有权。
        """
        config = session.config if isinstance(session.config, dict) else {}
        mcp = config.get("mcp_config") or {}
        enabled = mcp.get("enabled_servers")
        if not isinstance(enabled, list):
            enabled = []
        return {"enabled_servers": [str(s) for s in enabled]}

    async def update_session_mcp_config(self, session_id: str, enabled_servers: list[str]) -> dict:
        """更新会话的 MCP 配置（enabled_servers）。"""
        await self.get_session_or_raise(session_id)  # 校验存在
        await self.session_repo.update_config(
            uuid.UUID(session_id),
            {"mcp_config": {"enabled_servers": enabled_servers}},
        )
        return {"enabled_servers": enabled_servers}

    async def update_session_chat_model_ref(
        self, session_id: str, model_ref: str | None, *, flush: bool = True
    ) -> None:
        """更新会话存储的对话模型引用（系统模型 id 或用户模型 UUID）。"""
        await self.get_session_or_raise(session_id)
        await self.session_repo.update_config(
            uuid.UUID(session_id),
            {"chat_model_ref": model_ref},
            flush=flush,
        )

    async def merge_session_config_fragment(
        self, session_id: str, fragment: dict[str, Any], *, flush: bool = True
    ) -> None:
        """浅合并写入会话 config 片段。"""
        await self.get_session_or_raise(session_id)
        await self.session_repo.update_config(uuid.UUID(session_id), fragment, flush=flush)

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

    async def assert_session_accessible(
        self,
        session: Session,
        *,
        principal_id: str,
        is_anonymous: bool,
        role: str = "user",
    ) -> None:
        """断言当前主体可访问该会话（personal tenant 等值；平台 admin 放行）。"""
        owner = SessionOwner.from_principal_id(principal_id, is_anonymous)
        expected_tenant = await self._tenant_id_for_owner(owner)
        if not can_access_personal_session(
            session,
            personal_tenant_id=expected_tenant,
            is_platform_admin=role == Role.ADMIN.value,
        ):
            raise PermissionDeniedError(
                message="You don't have permission to access this session",
                resource="Session",
            )

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

        expected_tenant = await self._tenant_id_for_owner(owner)
        if not self.domain_service.check_tenant_ownership(session, expected_tenant):
            raise PermissionDeniedError(
                message="You don't have permission to access this session",
                resource="Session",
            )

        return session

    async def get_or_create_session_for_principal(
        self,
        principal_id: str,
        session_id: str | None = None,
        *,
        title: str | None = None,
        agent_id: str | None = None,
    ) -> tuple[Session, bool]:
        """按 Principal 获取或创建会话（含所有权校验）

        供 Chat、视频任务等用例复用，统一「无 session_id 则创建、有则校验所有权」的逻辑。

        Args:
            principal_id: 当前用户 Principal ID（与 Chat 一致，含 anonymous- 前缀时表示匿名）
            session_id: 会话 ID；若为 None 则创建新会话
            title: 新建会话时的标题（可选）
            agent_id: 新建会话时关联的 Agent ID（可选）

        Returns:
            (会话, 是否新建)

        Raises:
            NotFoundError: session_id 对应会话不存在
            PermissionDeniedError: session_id 对应会话不属于当前用户
        """
        is_anonymous = Principal.is_anonymous_id(principal_id)
        owner = SessionOwner.from_principal_id(principal_id, is_anonymous)

        if not session_id:
            session = await self.create_session(
                user_id=str(owner.user_id) if owner.user_id else None,
                anonymous_user_id=owner.anonymous_user_id,
                agent_id=agent_id,
                title=title,
            )
            return session, True

        session = await self.get_session_with_ownership_check(session_id, owner)
        return session, False

    # =========================================================================
    # Message Management
    # =========================================================================

    async def get_messages(
        self,
        session_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[MessageEntity]:
        """获取会话的消息列表"""
        return await self.message_service.find_by_session(
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
    ) -> MessageEntity:
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
        message = await self.message_service.create(
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
        return await self.message_service.count_by_session(uuid.UUID(session_id))

    async def count_total(self) -> int:
        """统计会话总数"""
        return await self.session_repo.count_total()

    async def count_active_today(self) -> int:
        """统计今日活跃会话数"""
        return await self.session_repo.count_active_today()

    async def count_by_user(self, user_id: str) -> int:
        """统计指定用户的会话数"""
        return await self.session_repo.count_by_user(uuid.UUID(user_id))

    async def sum_tokens_by_user(self, user_id: str) -> int:
        """统计指定用户所有会话 token 总量"""
        return await self.session_repo.sum_tokens_by_user(uuid.UUID(user_id))

    async def list_session_ids_by_user(self, user_id: str) -> list[uuid.UUID]:
        """列出指定用户的会话 ID"""
        return await self.session_repo.list_ids_by_user(uuid.UUID(user_id))

    async def reassign_anonymous_to_user(
        self,
        *,
        user_id: uuid.UUID | str,
        anonymous_user_id: str,
    ) -> int:
        """把匿名会话归并到正式用户"""
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        return await self.session_repo.reassign_anonymous_to_user(
            user_id=uid,
            anonymous_user_id=anonymous_user_id,
        )

    async def increment_video_task_count(self, session_id: str, count: int = 1) -> None:
        """增加会话的视频任务计数

        Args:
            session_id: 会话 ID
            count: 视频任务增量
        """
        await self.session_repo.increment_video_task_count(uuid.UUID(session_id), count)
