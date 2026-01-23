"""沙箱生命周期适配器 - 适配现有 SessionManager

实现 SandboxLifecycleService 接口，内部委托给现有的 SessionManager。
遵循适配器模式，将现有实现转换为领域层期望的接口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.agent.domain.entities.user_quota import UserQuota
from domains.agent.domain.services.sandbox_lifecycle import (
    SandboxInfo,
    SandboxState,
)
from domains.agent.infrastructure.sandbox.session_manager import (
    CleanupReason,
    SessionPolicy,
    SessionState,
)
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.agent.infrastructure.sandbox.session_manager import (
        SessionInfo,
        SessionManager,
        SessionRecreationResult,
    )

logger = get_logger(__name__)


class SandboxLifecycleAdapter:
    """沙箱生命周期适配器

    实现 SandboxLifecycleService 接口，
    内部委托给现有的 SessionManager。

    这个适配器的目的是：
    1. 将 SessionManager 的实现细节隐藏在接口后面
    2. 将 UserQuota 业务规则转换为 SessionPolicy 技术配置
    3. 将 SessionInfo 转换为 SandboxInfo 领域类型
    """

    def __init__(self, session_manager: SessionManager) -> None:
        """初始化适配器

        Args:
            session_manager: 现有的 SessionManager 实例
        """
        self._manager = session_manager

    async def cleanup_by_session(self, session_id: str) -> bool:
        """清理会话关联的沙箱

        Args:
            session_id: 会话 ID（conversation_id）

        Returns:
            是否成功清理
        """
        # 从 conversation_sessions 映射中查找沙箱 ID
        sandbox_id = self._manager._conversation_sessions.get(session_id)
        if sandbox_id:
            await self._manager.end_session(sandbox_id, CleanupReason.USER_REQUEST)
            logger.info(
                "Cleaned up sandbox %s for session %s",
                sandbox_id,
                session_id,
            )
            return True
        logger.debug("No sandbox found for session %s", session_id)
        return False

    async def ensure_available(
        self,
        session_id: str,
        user_id: str,
        quota: UserQuota,
    ) -> SandboxInfo:
        """确保会话有可用沙箱

        如果沙箱不存在则创建，如果超配额则由 SessionManager 自动驱逐旧的。

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            quota: 用户配额

        Returns:
            沙箱信息
        """
        # 保存原始策略
        original_policy = self._manager.policy

        # 将 UserQuota 转换为 SessionPolicy
        # 这里创建一个临时策略，只覆盖与配额相关的参数
        temp_policy = SessionPolicy(
            idle_timeout=quota.sandbox_idle_timeout,
            max_session_duration=quota.sandbox_max_duration,
            max_sessions_per_user=quota.max_sandboxes,
            # 保持其他参数不变
            disconnect_timeout=original_policy.disconnect_timeout,
            completion_retain=original_policy.completion_retain,
            max_total_sessions=original_policy.max_total_sessions,
            allow_session_reuse=original_policy.allow_session_reuse,
        )

        try:
            # 临时替换策略
            self._manager.policy = temp_policy

            # 使用 SessionManager 获取或创建沙箱
            result = await self._manager.get_or_create_session_with_info(
                user_id=user_id,
                conversation_id=session_id,
            )

            logger.debug(
                "Ensured sandbox for session %s: sandbox_id=%s, is_new=%s, is_recreated=%s",
                session_id,
                result.session.session_id,
                result.is_new,
                result.is_recreated,
            )

            return self._to_sandbox_info(result.session, result)
        finally:
            # 恢复原始策略
            self._manager.policy = original_policy

    async def get_by_session(self, session_id: str) -> SandboxInfo | None:
        """获取会话关联的沙箱

        Args:
            session_id: 会话 ID

        Returns:
            沙箱信息，如果不存在返回 None
        """
        sandbox_id = self._manager._conversation_sessions.get(session_id)
        if sandbox_id:
            session = await self._manager.get_session(sandbox_id)
            if session:
                return self._to_sandbox_info(session)
        return None

    async def count_user_sandboxes(self, user_id: str) -> int:
        """获取用户当前沙箱数量

        Args:
            user_id: 用户 ID

        Returns:
            用户当前拥有的沙箱数量
        """
        sessions = self._manager.get_user_sessions(user_id)
        return len(sessions)

    async def get_sandbox_state(self, session_id: str) -> SandboxState | None:
        """获取沙箱状态（用于持久化恢复）

        Args:
            session_id: 会话 ID

        Returns:
            沙箱状态，如果没有历史记录返回 None
        """
        history = self._manager._session_history.get(session_id)
        if history:
            return SandboxState(
                session_id=session_id,
                installed_packages=history.installed_packages.copy(),
                created_files=history.created_files.copy(),
                cleanup_reason=(
                    history.cleanup_reason.value if history.cleanup_reason else None
                ),
                cleaned_at=history.last_cleaned_at,
            )
        return None

    def _to_sandbox_info(
        self,
        session: SessionInfo,
        result: SessionRecreationResult | None = None,
    ) -> SandboxInfo:
        """将 SessionInfo 转换为 SandboxInfo

        Args:
            session: SessionManager 的会话信息
            result: 创建/获取结果（可选）

        Returns:
            领域层的沙箱信息
        """
        return SandboxInfo(
            sandbox_id=session.session_id,
            session_id=session.conversation_id or "",
            user_id=session.user_id,
            is_active=session.state in (SessionState.ACTIVE, SessionState.IDLE),
            created_at=session.created_at,
            last_activity=session.last_activity,
            is_recreated=result.is_recreated if result else False,
            recreation_message=result.message if result else None,
            installed_packages=session.installed_packages.copy(),
            created_files=session.created_files.copy(),
        )
