"""
Session Manager - 会话管理器

统一管理 Docker 沙箱会话的生命周期：
- 会话创建与复用
- 多种清理策略
- 资源限制与 LRU 淘汰
- 用户/对话关联
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

# 运行时需要的导入
from core.sandbox.session_executor_factory import (
    DefaultSessionExecutorFactory,
    SessionExecutorFactory,
)
from utils.logging import get_logger

# 类型注解导入（使用 TYPE_CHECKING 以满足 linter 要求）
# 注意：虽然不存在循环依赖，但 linter 建议将仅用于类型注解的导入放在 TYPE_CHECKING 中
if TYPE_CHECKING:
    from core.sandbox.executor import SandboxConfig, SessionDockerExecutor

logger = get_logger(__name__)


class SessionState(str, Enum):
    """会话状态"""

    CREATING = "creating"  # 正在创建
    ACTIVE = "active"  # 活跃中
    IDLE = "idle"  # 空闲
    COMPLETING = "completing"  # 任务完成，等待清理
    DISCONNECTED = "disconnected"  # 连接断开，等待重连
    EXPIRED = "expired"  # 已过期
    ERROR = "error"  # 错误状态
    RECREATED = "recreated"  # 重新创建（之前的已清理）


class CleanupReason(str, Enum):
    """清理原因"""

    USER_REQUEST = "user_request"  # 用户主动结束
    TASK_COMPLETE = "task_complete"  # 任务完成
    IDLE_TIMEOUT = "idle_timeout"  # 空闲超时
    DISCONNECT_TIMEOUT = "disconnect_timeout"  # 断开超时
    RESOURCE_LIMIT = "resource_limit"  # 资源限制（LRU）
    APP_SHUTDOWN = "app_shutdown"  # 应用关闭
    ERROR = "error"  # 错误
    ORPHAN = "orphan"  # 孤儿会话


@dataclass
class SessionPolicy:
    """会话策略配置"""

    # 空闲超时（秒）- 无活动后多久清理
    idle_timeout: int = 7200  # 2 小时（更友好的默认值）

    # 断开超时（秒）- 断开连接后等待重连时间
    disconnect_timeout: int = 1800  # 30 分钟（允许临时离开）

    # 任务完成后保留时间（秒）- 方便用户查看结果
    completion_retain: int = 3600  # 1 小时

    # 最大会话时长（秒）- 硬性限制
    max_session_duration: int = 28800  # 8 小时（支持长时间工作）

    # 每用户最大会话数
    max_sessions_per_user: int = 5

    # 全局最大会话数
    max_total_sessions: int = 200

    # 是否允许会话复用（同一对话复用容器）
    allow_session_reuse: bool = True


@dataclass
class SessionHistory:
    """会话历史记录（用于环境重建）"""

    conversation_id: str
    user_id: str | None = None

    # 上一次会话的信息
    last_session_id: str | None = None
    last_cleaned_at: datetime | None = None
    cleanup_reason: CleanupReason | None = None

    # 环境快照（用于提示或恢复）
    installed_packages: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    environment_variables: dict[str, str] = field(default_factory=dict)

    # 统计
    total_sessions: int = 0
    total_commands: int = 0


@dataclass
class SessionInfo:
    """会话信息"""

    session_id: str
    user_id: str | None = None
    conversation_id: str | None = None
    state: SessionState = SessionState.CREATING
    executor: SessionDockerExecutor | None = None

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    state_changed_at: datetime = field(default_factory=datetime.now)

    # 统计信息
    command_count: int = 0
    total_duration_ms: int = 0

    # 环境状态追踪
    installed_packages: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)

    # 是否是重建的会话
    is_recreated: bool = False
    previous_session_id: str | None = None

    def update_activity(self) -> None:
        """更新最后活动时间"""
        self.last_activity = datetime.now()
        if self.state == SessionState.IDLE:
            self.state = SessionState.ACTIVE
            self.state_changed_at = datetime.now()

    def set_state(self, state: SessionState) -> None:
        """设置状态"""
        self.state = state
        self.state_changed_at = datetime.now()

    def record_package_install(self, package: str) -> None:
        """记录包安装"""
        if package not in self.installed_packages:
            self.installed_packages.append(package)

    def record_file_creation(self, filepath: str) -> None:
        """记录文件创建"""
        if filepath not in self.created_files:
            self.created_files.append(filepath)


@dataclass
class SessionRecreationResult:
    """会话重建结果"""

    session: SessionInfo
    is_new: bool  # 是否是新创建的
    is_recreated: bool  # 是否是重建的（之前被清理过）
    previous_state: SessionHistory | None  # 之前的状态信息
    message: str | None  # 给用户的提示消息


class SessionManager:
    """
    会话管理器

    负责：
    1. 会话创建与获取
    2. 会话状态管理
    3. 多种清理策略执行
    4. 资源限制与 LRU 淘汰
    5. 会话重建与状态恢复提示
    """

    _instance: ClassVar[SessionManager | None] = None

    def __init__(
        self,
        policy: SessionPolicy | None = None,
        executor_factory: SessionExecutorFactory | None = None,
    ) -> None:
        """
        初始化会话管理器

        Args:
            policy: 会话策略配置
            executor_factory: 会话执行器工厂（用于依赖注入，默认使用 DefaultSessionExecutorFactory）
        """
        self.policy = policy or SessionPolicy()
        self.executor_factory = executor_factory
        self._sessions: dict[str, SessionInfo] = {}
        self._user_sessions: dict[str, set[str]] = {}  # user_id -> session_ids
        self._conversation_sessions: dict[str, str] = {}  # conversation_id -> session_id
        self._session_history: dict[str, SessionHistory] = {}  # conversation_id -> history
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    @classmethod
    def get_instance(
        cls,
        policy: SessionPolicy | None = None,
        executor_factory: SessionExecutorFactory | None = None,
    ) -> SessionManager:
        """
        获取单例实例

        Args:
            policy: 会话策略配置
            executor_factory: 会话执行器工厂（仅在首次创建时生效）
        """
        if cls._instance is None:
            cls._instance = cls(policy, executor_factory)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅用于测试）"""
        cls._instance = None

    async def start(self) -> None:
        """启动会话管理器"""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SessionManager started")

    async def stop(self) -> None:
        """停止会话管理器"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # 清理所有会话
        await self.cleanup_all(CleanupReason.APP_SHUTDOWN)
        logger.info("SessionManager stopped")

    async def get_or_create_session(
        self,
        user_id: str | None = None,
        conversation_id: str | None = None,
        config: SandboxConfig | None = None,
    ) -> SessionInfo:
        """
        获取或创建会话

        如果启用会话复用且存在活跃会话，则复用；否则创建新会话。
        简化接口，内部调用 get_or_create_session_with_info
        """
        result = await self.get_or_create_session_with_info(user_id, conversation_id, config)
        return result.session

    async def get_or_create_session_with_info(
        self,
        user_id: str | None = None,
        conversation_id: str | None = None,
        config: SandboxConfig | None = None,
    ) -> SessionRecreationResult:
        """
        获取或创建会话（带详细信息）

        返回会话以及是否是重建的、之前的状态等信息，
        便于前端展示适当的提示。
        """
        async with self._lock:
            # 检查是否可以复用现有会话
            if self.policy.allow_session_reuse and conversation_id:
                existing_session_id = self._conversation_sessions.get(conversation_id)
                if existing_session_id and existing_session_id in self._sessions:
                    session = self._sessions[existing_session_id]
                    if session.state in (SessionState.ACTIVE, SessionState.IDLE):
                        session.update_activity()
                        logger.debug(
                            "Reusing session %s for conversation %s",
                            session.session_id,
                            conversation_id,
                        )
                        return SessionRecreationResult(
                            session=session,
                            is_new=False,
                            is_recreated=False,
                            previous_state=None,
                            message=None,
                        )

            # 检查是否有历史记录（之前被清理过）
            history = self._session_history.get(conversation_id) if conversation_id else None

            # 检查资源限制
            await self._enforce_resource_limits(user_id)

            # 创建新会话
            session = await self._create_session(user_id, conversation_id, config)

            # 如果有历史记录，标记为重建的会话
            if history:
                session.is_recreated = True
                session.previous_session_id = history.last_session_id
                session.set_state(SessionState.RECREATED)

                # 生成用户提示消息
                message = self._generate_recreation_message(history)

                # 更新历史记录
                history.total_sessions += 1

                logger.info(
                    "Recreated session %s for conversation %s (previous: %s, cleaned: %s)",
                    session.session_id,
                    conversation_id,
                    history.last_session_id,
                    history.cleanup_reason,
                )

                return SessionRecreationResult(
                    session=session,
                    is_new=False,
                    is_recreated=True,
                    previous_state=history,
                    message=message,
                )

            # 全新会话
            if conversation_id:
                self._session_history[conversation_id] = SessionHistory(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    total_sessions=1,
                )

            return SessionRecreationResult(
                session=session,
                is_new=True,
                is_recreated=False,
                previous_state=None,
                message=None,
            )

    def _generate_recreation_message(self, history: SessionHistory) -> str:
        """生成会话重建的用户提示消息"""
        parts = ["执行环境已重置"]

        # 说明清理原因
        reason_messages = {
            CleanupReason.IDLE_TIMEOUT: "（由于长时间未活动）",
            CleanupReason.DISCONNECT_TIMEOUT: "（由于连接断开超时）",
            CleanupReason.TASK_COMPLETE: "（任务已完成）",
            CleanupReason.RESOURCE_LIMIT: "（由于系统资源限制）",
            CleanupReason.USER_REQUEST: "",
            CleanupReason.APP_SHUTDOWN: "（由于服务重启）",
            CleanupReason.ERROR: "（由于执行错误）",
        }
        if history.cleanup_reason:
            parts.append(reason_messages.get(history.cleanup_reason, ""))

        # 提示丢失的状态
        lost_items = []
        if history.installed_packages:
            pkg_str = ", ".join(history.installed_packages[:3])
            if len(history.installed_packages) > 3:
                pkg_str += f" 等 {len(history.installed_packages)} 个包"
            lost_items.append(f"已安装的包 ({pkg_str})")

        if history.created_files:
            file_count = len(history.created_files)
            lost_items.append(f"创建的文件 ({file_count} 个)")

        if lost_items:
            parts.append("。以下内容需要重新设置：")
            parts.append("、".join(lost_items))
        else:
            parts.append("。")

        return "".join(parts)

    async def _create_session(
        self,
        user_id: str | None,
        conversation_id: str | None,
        config: SandboxConfig | None,
    ) -> SessionInfo:
        """创建新会话（内部方法，需要在锁内调用）"""
        # 使用工厂创建执行器（支持依赖注入）
        if self.executor_factory is None:
            self.executor_factory = DefaultSessionExecutorFactory()

        executor = self.executor_factory.create_session_executor(
            max_idle_seconds=self.policy.idle_timeout,
            config=config,
        )

        # 先创建 SessionInfo，获取 session_id
        await executor.start_session(config)
        session_id = executor.session_id or ""

        session = SessionInfo(
            session_id=session_id,
            user_id=user_id,
            conversation_id=conversation_id,
            state=SessionState.ACTIVE,
            executor=executor,
        )

        # 注册会话
        self._sessions[session_id] = session

        if user_id:
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = set()
            self._user_sessions[user_id].add(session_id)

        if conversation_id:
            self._conversation_sessions[conversation_id] = session_id

        logger.info(
            "Created session %s for user=%s, conversation=%s",
            session_id,
            user_id,
            conversation_id,
        )
        return session

    async def _enforce_resource_limits(self, user_id: str | None) -> None:
        """强制执行资源限制（内部方法，需要在锁内调用）"""
        # 检查全局限制
        if len(self._sessions) >= self.policy.max_total_sessions:
            # 触发 LRU 清理
            await self._cleanup_lru(1)

        # 检查用户限制
        if user_id and user_id in self._user_sessions:
            user_session_count = len(self._user_sessions[user_id])
            if user_session_count >= self.policy.max_sessions_per_user:
                # 清理该用户最旧的会话
                await self._cleanup_user_oldest(user_id)

    async def _cleanup_lru(self, count: int) -> None:
        """清理最近最少使用的会话"""
        # 按最后活动时间排序
        sorted_sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.last_activity,
        )

        cleaned = 0
        for session in sorted_sessions:
            if cleaned >= count:
                break
            if session.state not in (SessionState.CREATING, SessionState.ACTIVE):
                await self._remove_session(session.session_id, CleanupReason.RESOURCE_LIMIT)
                cleaned += 1

        # 如果没有非活跃会话可清理，清理最旧的空闲会话
        if cleaned < count:
            for session in sorted_sessions:
                if cleaned >= count:
                    break
                if session.state == SessionState.IDLE:
                    await self._remove_session(session.session_id, CleanupReason.RESOURCE_LIMIT)
                    cleaned += 1

    async def _cleanup_user_oldest(self, user_id: str) -> None:
        """清理用户最旧的会话"""
        session_ids = self._user_sessions.get(user_id, set())
        if not session_ids:
            return

        oldest_session: SessionInfo | None = None
        oldest_time = datetime.now()

        for session_id in session_ids:
            session = self._sessions.get(session_id)
            if session and session.last_activity < oldest_time:
                oldest_time = session.last_activity
                oldest_session = session

        if oldest_session:
            await self._remove_session(oldest_session.session_id, CleanupReason.RESOURCE_LIMIT)

    async def get_session(self, session_id: str) -> SessionInfo | None:
        """获取会话信息"""
        return self._sessions.get(session_id)

    async def update_session_activity(self, session_id: str) -> None:
        """更新会话活动时间"""
        session = self._sessions.get(session_id)
        if session:
            session.update_activity()

    async def mark_session_complete(self, session_id: str) -> None:
        """标记会话任务完成"""
        session = self._sessions.get(session_id)
        if session:
            session.set_state(SessionState.COMPLETING)
            logger.debug("Session %s marked as completing", session_id)

    async def mark_session_disconnected(self, session_id: str) -> None:
        """标记会话断开连接"""
        session = self._sessions.get(session_id)
        if session and session.state == SessionState.ACTIVE:
            session.set_state(SessionState.DISCONNECTED)
            logger.debug("Session %s marked as disconnected", session_id)

    async def mark_session_reconnected(self, session_id: str) -> None:
        """标记会话重新连接"""
        session = self._sessions.get(session_id)
        if session and session.state == SessionState.DISCONNECTED:
            session.set_state(SessionState.ACTIVE)
            session.update_activity()
            logger.debug("Session %s reconnected", session_id)

    async def mark_session_idle(self, session_id: str) -> None:
        """标记会话空闲"""
        session = self._sessions.get(session_id)
        if session and session.state == SessionState.ACTIVE:
            session.set_state(SessionState.IDLE)

    async def record_command_execution(
        self,
        session_id: str,
        command: str,
        duration_ms: int = 0,
    ) -> None:
        """记录命令执行"""
        session = self._sessions.get(session_id)
        if session:
            session.command_count += 1
            session.total_duration_ms += duration_ms
            session.update_activity()

            # 检测包安装命令
            self._detect_package_install(session, command)

            # 检测文件创建
            self._detect_file_creation(session, command)

    def _detect_package_install(self, session: SessionInfo, command: str) -> None:
        """检测并记录包安装"""
        command_lower = command.lower().strip()

        # pip install
        if "pip install" in command_lower or "pip3 install" in command_lower:
            # 提取包名（简单解析）
            parts = command.split()
            for i, part in enumerate(parts):
                if part in ("install",) and i + 1 < len(parts):
                    pkg = parts[i + 1]
                    if not pkg.startswith("-"):
                        session.record_package_install(pkg.split("==")[0].split(">=")[0])

        # npm install
        elif "npm install" in command_lower or "npm i " in command_lower:
            parts = command.split()
            for i, part in enumerate(parts):
                if part in ("install", "i") and i + 1 < len(parts):
                    pkg = parts[i + 1]
                    if not pkg.startswith("-"):
                        session.record_package_install(f"npm:{pkg}")

        # apt install
        elif "apt install" in command_lower or "apt-get install" in command_lower:
            parts = command.split()
            for i, part in enumerate(parts):
                if part == "install" and i + 1 < len(parts):
                    pkg = parts[i + 1]
                    if not pkg.startswith("-"):
                        session.record_package_install(f"apt:{pkg}")

    def _detect_file_creation(self, session: SessionInfo, command: str) -> None:
        """检测并记录文件创建"""
        # 简单检测：重定向输出、touch、mkdir 等
        if ">" in command and ">>" not in command:
            # 输出重定向，提取文件路径
            parts = command.split(">")
            if len(parts) >= 2:
                filepath = parts[-1].strip().split()[0] if parts[-1].strip() else None
                if filepath:
                    session.record_file_creation(filepath)

        elif command.strip().startswith("touch "):
            filepath = command.strip()[6:].split()[0]
            session.record_file_creation(filepath)

        elif "mkdir " in command:
            # 提取目录名（跳过选项如 -p）
            parts = command.split()
            for i, part in enumerate(parts):
                if part == "mkdir":
                    # 找到 mkdir 后的非选项参数
                    for j in range(i + 1, len(parts)):
                        if not parts[j].startswith("-"):
                            session.record_file_creation(parts[j] + "/")
                            break
                    break

    async def end_session(
        self,
        session_id: str,
        reason: CleanupReason = CleanupReason.USER_REQUEST,
    ) -> None:
        """结束会话"""
        async with self._lock:
            await self._remove_session(session_id, reason)

    async def _remove_session(self, session_id: str, reason: CleanupReason) -> None:
        """移除会话（内部方法，需要在锁内调用）"""
        session = self._sessions.pop(session_id, None)
        if not session:
            return

        # 保存会话历史（用于后续重建时提示用户）
        if session.conversation_id:
            history = self._session_history.get(session.conversation_id)
            if history:
                history.last_session_id = session_id
                history.last_cleaned_at = datetime.now()
                history.cleanup_reason = reason
                history.installed_packages = session.installed_packages.copy()
                history.created_files = session.created_files.copy()
                history.total_commands += session.command_count
            else:
                self._session_history[session.conversation_id] = SessionHistory(
                    conversation_id=session.conversation_id,
                    user_id=session.user_id,
                    last_session_id=session_id,
                    last_cleaned_at=datetime.now(),
                    cleanup_reason=reason,
                    installed_packages=session.installed_packages.copy(),
                    created_files=session.created_files.copy(),
                    total_sessions=1,
                    total_commands=session.command_count,
                )

        # 清理关联映射
        if session.user_id and session.user_id in self._user_sessions:
            self._user_sessions[session.user_id].discard(session_id)
            if not self._user_sessions[session.user_id]:
                del self._user_sessions[session.user_id]

        if session.conversation_id:
            self._conversation_sessions.pop(session.conversation_id, None)

        # 停止执行器
        if session.executor:
            try:
                await session.executor.stop_session()
            except Exception as e:
                logger.warning("Error stopping session %s: %s", session_id, e)

        logger.info(
            "Removed session %s, reason=%s, duration=%s, commands=%d, packages=%d, files=%d",
            session_id,
            reason.value,
            datetime.now() - session.created_at,
            session.command_count,
            len(session.installed_packages),
            len(session.created_files),
        )

    async def cleanup_all(self, reason: CleanupReason) -> int:
        """清理所有会话"""
        async with self._lock:
            session_ids = list(self._sessions.keys())
            for session_id in session_ids:
                await self._remove_session(session_id, reason)
            return len(session_ids)

    async def _cleanup_loop(self) -> None:
        """清理循环"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._check_and_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup loop error: %s", e)

    async def _check_and_cleanup(self) -> None:
        """检查并清理过期会话"""
        now = datetime.now()
        to_cleanup: list[tuple[str, CleanupReason]] = []

        async with self._lock:
            for session_id, session in list(self._sessions.items()):
                cleanup_reason = self._should_cleanup(session, now)
                if cleanup_reason:
                    to_cleanup.append((session_id, cleanup_reason))

            for session_id, reason in to_cleanup:
                await self._remove_session(session_id, reason)

        if to_cleanup:
            logger.info("Cleaned up %d sessions", len(to_cleanup))

    def _should_cleanup(self, session: SessionInfo, now: datetime) -> CleanupReason | None:
        """判断会话是否应该清理"""
        # 最大会话时长
        session_duration = (now - session.created_at).total_seconds()
        if session_duration > self.policy.max_session_duration:
            return CleanupReason.IDLE_TIMEOUT

        # 根据状态判断
        state_duration = (now - session.state_changed_at).total_seconds()
        idle_duration = (now - session.last_activity).total_seconds()

        if session.state == SessionState.COMPLETING:
            if state_duration > self.policy.completion_retain:
                return CleanupReason.TASK_COMPLETE

        elif session.state == SessionState.DISCONNECTED:
            if state_duration > self.policy.disconnect_timeout:
                return CleanupReason.DISCONNECT_TIMEOUT

        elif session.state in (SessionState.ACTIVE, SessionState.IDLE):
            if idle_duration > self.policy.idle_timeout:
                return CleanupReason.IDLE_TIMEOUT

        elif session.state == SessionState.ERROR:
            return CleanupReason.ERROR

        return None

    # =========================================================================
    # 统计与监控
    # =========================================================================

    def get_stats(self) -> dict:
        """获取统计信息"""
        state_counts: dict[str, int] = {}
        for session in self._sessions.values():
            state_counts[session.state.value] = state_counts.get(session.state.value, 0) + 1

        return {
            "total_sessions": len(self._sessions),
            "total_users": len(self._user_sessions),
            "state_counts": state_counts,
            "policy": {
                "idle_timeout": self.policy.idle_timeout,
                "max_sessions_per_user": self.policy.max_sessions_per_user,
                "max_total_sessions": self.policy.max_total_sessions,
            },
        }

    def get_user_sessions(self, user_id: str) -> list[SessionInfo]:
        """获取用户的所有会话"""
        session_ids = self._user_sessions.get(user_id, set())
        return [self._sessions[sid] for sid in session_ids if sid in self._sessions]
