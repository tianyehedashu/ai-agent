"""
Sandbox Manager - 沙箱管理器

统一管理 Docker 沙箱的生命周期：
- 沙箱创建与复用
- 多种清理策略
- 资源限制与 LRU 淘汰
- 用户/会话关联
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import os
import shutil
from typing import TYPE_CHECKING, ClassVar

# 运行时需要的导入
from domains.agent.infrastructure.sandbox.sandbox_executor_factory import (
    DefaultSandboxExecutorFactory,
    SandboxExecutorFactory,
)
from utils.logging import get_logger

# 类型注解导入（使用 TYPE_CHECKING 以满足 linter 要求）
# 注意：虽然不存在循环依赖，但 linter 建议将仅用于类型注解的导入放在 TYPE_CHECKING 中
if TYPE_CHECKING:
    from domains.agent.infrastructure.sandbox.executor import (
        PersistentDockerExecutor,
        SandboxConfig,
    )
    from libs.config.execution_config import SandboxPolicyConfig

logger = get_logger(__name__)


class SandboxRunState(str, Enum):
    """沙箱运行状态"""

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
    ORPHAN = "orphan"  # 孤儿沙箱


@dataclass
class SandboxPolicy:
    """沙箱策略配置"""

    # 空闲超时（秒）- 无活动后多久清理
    idle_timeout: int = 7200  # 2 小时（更友好的默认值）

    # 断开超时（秒）- 断开连接后等待重连时间
    disconnect_timeout: int = 1800  # 30 分钟（允许临时离开）

    # 任务完成后保留时间（秒）- 方便用户查看结果
    completion_retain: int = 3600  # 1 小时

    # 最大沙箱时长（秒）- 硬性限制
    max_sandbox_duration: int = 28800  # 8 小时（支持长时间工作）

    # 每用户最大沙箱数
    max_sandboxes_per_user: int = 5

    # 全局最大沙箱数
    max_total_sandboxes: int = 200

    # 是否允许沙箱复用（同一会话复用容器）
    allow_sandbox_reuse: bool = True

    # 沙箱结束时是否删除工作目录（默认删除，防止目录爆炸）
    cleanup_workspace_on_sandbox_end: bool = True

    @classmethod
    def from_config(cls, config: SandboxPolicyConfig) -> SandboxPolicy:
        """从配置模型构建策略（单一入口，避免各处手写字段拷贝）。

        Args:
            config: 来自 ExecutionConfig 的沙箱策略配置。

        Returns:
            SandboxPolicy 实例。
        """
        return cls(**config.model_dump())


@dataclass
class SandboxHistory:
    """沙箱历史记录（用于环境重建）"""

    session_id: str
    user_id: str | None = None

    # 上一次沙箱的信息
    last_sandbox_id: str | None = None
    last_cleaned_at: datetime | None = None
    cleanup_reason: CleanupReason | None = None

    # 环境快照（用于提示或恢复）
    installed_packages: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    environment_variables: dict[str, str] = field(default_factory=dict)

    # 统计
    total_sandboxes: int = 0
    total_commands: int = 0


@dataclass
class SandboxContext:
    """沙箱上下文信息"""

    sandbox_id: str
    user_id: str | None = None
    session_id: str | None = None
    state: SandboxRunState = SandboxRunState.CREATING
    executor: PersistentDockerExecutor | None = None

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

    # 是否是重建的沙箱
    is_recreated: bool = False
    previous_sandbox_id: str | None = None

    def update_activity(self) -> None:
        """更新最后活动时间"""
        self.last_activity = datetime.now()
        if self.state == SandboxRunState.IDLE:
            self.state = SandboxRunState.ACTIVE
            self.state_changed_at = datetime.now()

    def set_state(self, state: SandboxRunState) -> None:
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
class SandboxCreationResult:
    """沙箱创建结果"""

    sandbox: SandboxContext
    is_new: bool  # 是否是新创建的
    is_recreated: bool  # 是否是重建的（之前被清理过）
    previous_state: SandboxHistory | None  # 之前的状态信息
    message: str | None  # 给用户的提示消息


class SandboxManager:
    """
    沙箱管理器

    负责：
    1. 沙箱创建与获取
    2. 沙箱状态管理
    3. 多种清理策略执行
    4. 资源限制与 LRU 淘汰
    5. 沙箱重建与状态恢复提示
    """

    _instance: ClassVar[SandboxManager | None] = None

    def __init__(
        self,
        policy: SandboxPolicy | None = None,
        executor_factory: SandboxExecutorFactory | None = None,
    ) -> None:
        """
        初始化沙箱管理器

        Args:
            policy: 沙箱策略配置
            executor_factory: 沙箱执行器工厂（用于依赖注入，默认使用 DefaultSandboxExecutorFactory）
        """
        self.policy = policy or SandboxPolicy()
        self.executor_factory = executor_factory
        self._sandboxes: dict[str, SandboxContext] = {}
        self._user_sandboxes: dict[str, set[str]] = {}  # user_id -> sandbox_ids
        self._session_sandboxes: dict[str, str] = {}  # session_id -> sandbox_id
        self._sandbox_history: dict[str, SandboxHistory] = {}  # session_id -> history
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    @classmethod
    def get_instance(
        cls,
        policy: SandboxPolicy | None = None,
        executor_factory: SandboxExecutorFactory | None = None,
    ) -> SandboxManager:
        """
        获取单例实例

        Args:
            policy: 沙箱策略配置
            executor_factory: 沙箱执行器工厂（仅在首次创建时生效）
        """
        if cls._instance is None:
            cls._instance = cls(policy, executor_factory)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅用于测试）"""
        cls._instance = None

    async def start(self) -> None:
        """启动沙箱管理器"""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SandboxManager started")

    async def stop(self) -> None:
        """停止沙箱管理器"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # 清理所有沙箱
        await self.cleanup_all(CleanupReason.APP_SHUTDOWN)
        logger.info("SandboxManager stopped")

    async def get_or_create(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        config: SandboxConfig | None = None,
    ) -> SandboxContext:
        """
        获取或创建沙箱

        如果启用沙箱复用且存在活跃沙箱，则复用；否则创建新沙箱。
        简化接口，内部调用 get_or_create_with_info
        """
        result = await self.get_or_create_with_info(user_id, session_id, config)
        return result.sandbox

    async def get_or_create_with_info(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        config: SandboxConfig | None = None,
    ) -> SandboxCreationResult:
        """
        获取或创建沙箱（带详细信息）

        返回沙箱以及是否是重建的、之前的状态等信息，
        便于前端展示适当的提示。
        """
        async with self._lock:
            # 检查是否可以复用现有沙箱
            if self.policy.allow_sandbox_reuse and session_id:
                existing_sandbox_id = self._session_sandboxes.get(session_id)
                if existing_sandbox_id and existing_sandbox_id in self._sandboxes:
                    sandbox = self._sandboxes[existing_sandbox_id]
                    if sandbox.state in (SandboxRunState.ACTIVE, SandboxRunState.IDLE):
                        sandbox.update_activity()
                        logger.debug(
                            "Reusing sandbox %s for session %s",
                            sandbox.sandbox_id,
                            session_id,
                        )
                        return SandboxCreationResult(
                            sandbox=sandbox,
                            is_new=False,
                            is_recreated=False,
                            previous_state=None,
                            message=None,
                        )

            # 检查是否有历史记录（之前被清理过）
            history = self._sandbox_history.get(session_id) if session_id else None

            # 检查资源限制
            await self._enforce_resource_limits(user_id)

            # 创建新沙箱
            sandbox = await self._create_sandbox(user_id, session_id, config)

            # 如果有历史记录，标记为重建的沙箱
            if history:
                sandbox.is_recreated = True
                sandbox.previous_sandbox_id = history.last_sandbox_id
                sandbox.set_state(SandboxRunState.RECREATED)

                # 生成用户提示消息
                message = self._generate_recreation_message(history)

                # 更新历史记录
                history.total_sandboxes += 1

                logger.info(
                    "Recreated sandbox %s for session %s (previous: %s, cleaned: %s)",
                    sandbox.sandbox_id,
                    session_id,
                    history.last_sandbox_id,
                    history.cleanup_reason,
                )

                return SandboxCreationResult(
                    sandbox=sandbox,
                    is_new=False,
                    is_recreated=True,
                    previous_state=history,
                    message=message,
                )

            # 全新沙箱
            if session_id:
                self._sandbox_history[session_id] = SandboxHistory(
                    session_id=session_id,
                    user_id=user_id,
                    total_sandboxes=1,
                )

            return SandboxCreationResult(
                sandbox=sandbox,
                is_new=True,
                is_recreated=False,
                previous_state=None,
                message=None,
            )

    def _generate_recreation_message(self, history: SandboxHistory) -> str:
        """生成沙箱重建的用户提示消息"""
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

    async def _create_sandbox(
        self,
        user_id: str | None,
        session_id: str | None,
        config: SandboxConfig | None,
    ) -> SandboxContext:
        """创建新沙箱（内部方法，需要在锁内调用）"""
        # 使用工厂创建执行器（支持依赖注入）
        if self.executor_factory is None:
            self.executor_factory = DefaultSandboxExecutorFactory()

        executor = self.executor_factory.create_sandbox_executor(
            max_idle_seconds=self.policy.idle_timeout,
            config=config,
        )

        # 先创建 SandboxContext，获取 sandbox_id
        await executor.start()
        sandbox_id = executor.sandbox_id or ""

        sandbox = SandboxContext(
            sandbox_id=sandbox_id,
            user_id=user_id,
            session_id=session_id,
            state=SandboxRunState.ACTIVE,
            executor=executor,
        )

        # 注册沙箱
        self._sandboxes[sandbox_id] = sandbox

        if user_id:
            if user_id not in self._user_sandboxes:
                self._user_sandboxes[user_id] = set()
            self._user_sandboxes[user_id].add(sandbox_id)

        if session_id:
            self._session_sandboxes[session_id] = sandbox_id

        logger.info(
            "Created sandbox %s for user=%s, session=%s",
            sandbox_id,
            user_id,
            session_id,
        )
        return sandbox

    async def _enforce_resource_limits(self, user_id: str | None) -> None:
        """强制执行资源限制（内部方法，需要在锁内调用）"""
        # 检查全局限制
        if len(self._sandboxes) >= self.policy.max_total_sandboxes:
            # 触发 LRU 清理
            await self._cleanup_lru(1)

        # 检查用户限制
        if user_id and user_id in self._user_sandboxes:
            user_sandbox_count = len(self._user_sandboxes[user_id])
            if user_sandbox_count >= self.policy.max_sandboxes_per_user:
                # 清理该用户最旧的沙箱
                await self._cleanup_user_oldest(user_id)

    async def _cleanup_lru(self, count: int) -> None:
        """清理最近最少使用的沙箱"""
        # 按最后活动时间排序
        sorted_sandboxes = sorted(
            self._sandboxes.values(),
            key=lambda s: s.last_activity,
        )

        cleaned = 0
        for sandbox in sorted_sandboxes:
            if cleaned >= count:
                break
            if sandbox.state not in (SandboxRunState.CREATING, SandboxRunState.ACTIVE):
                await self._remove_sandbox(sandbox.sandbox_id, CleanupReason.RESOURCE_LIMIT)
                cleaned += 1

        # 如果没有非活跃沙箱可清理，清理最旧的空闲沙箱
        if cleaned < count:
            for sandbox in sorted_sandboxes:
                if cleaned >= count:
                    break
                if sandbox.state == SandboxRunState.IDLE:
                    await self._remove_sandbox(sandbox.sandbox_id, CleanupReason.RESOURCE_LIMIT)
                    cleaned += 1

    async def _cleanup_user_oldest(self, user_id: str) -> None:
        """清理用户最旧的沙箱"""
        sandbox_ids = self._user_sandboxes.get(user_id, set())
        if not sandbox_ids:
            return

        oldest_sandbox: SandboxContext | None = None
        oldest_time = datetime.now()

        for sandbox_id in sandbox_ids:
            sandbox = self._sandboxes.get(sandbox_id)
            if sandbox and sandbox.last_activity < oldest_time:
                oldest_time = sandbox.last_activity
                oldest_sandbox = sandbox

        if oldest_sandbox:
            await self._remove_sandbox(oldest_sandbox.sandbox_id, CleanupReason.RESOURCE_LIMIT)

    async def get_sandbox(self, sandbox_id: str) -> SandboxContext | None:
        """获取沙箱信息"""
        return self._sandboxes.get(sandbox_id)

    async def update_sandbox_activity(self, sandbox_id: str) -> None:
        """更新沙箱活动时间"""
        sandbox = self._sandboxes.get(sandbox_id)
        if sandbox:
            sandbox.update_activity()

    async def mark_sandbox_complete(self, sandbox_id: str) -> None:
        """标记沙箱任务完成"""
        sandbox = self._sandboxes.get(sandbox_id)
        if sandbox:
            sandbox.set_state(SandboxRunState.COMPLETING)
            logger.debug("Sandbox %s marked as completing", sandbox_id)

    async def mark_sandbox_disconnected(self, sandbox_id: str) -> None:
        """标记沙箱断开连接"""
        sandbox = self._sandboxes.get(sandbox_id)
        if sandbox and sandbox.state == SandboxRunState.ACTIVE:
            sandbox.set_state(SandboxRunState.DISCONNECTED)
            logger.debug("Sandbox %s marked as disconnected", sandbox_id)

    async def mark_sandbox_reconnected(self, sandbox_id: str) -> None:
        """标记沙箱重新连接"""
        sandbox = self._sandboxes.get(sandbox_id)
        if sandbox and sandbox.state == SandboxRunState.DISCONNECTED:
            sandbox.set_state(SandboxRunState.ACTIVE)
            sandbox.update_activity()
            logger.debug("Sandbox %s reconnected", sandbox_id)

    async def mark_sandbox_idle(self, sandbox_id: str) -> None:
        """标记沙箱空闲"""
        sandbox = self._sandboxes.get(sandbox_id)
        if sandbox and sandbox.state == SandboxRunState.ACTIVE:
            sandbox.set_state(SandboxRunState.IDLE)

    async def record_command_execution(
        self,
        sandbox_id: str,
        command: str,
        duration_ms: int = 0,
    ) -> None:
        """记录命令执行"""
        sandbox = self._sandboxes.get(sandbox_id)
        if sandbox:
            sandbox.command_count += 1
            sandbox.total_duration_ms += duration_ms
            sandbox.update_activity()

            # 检测包安装命令
            self._detect_package_install(sandbox, command)

            # 检测文件创建
            self._detect_file_creation(sandbox, command)

    def _detect_package_install(self, sandbox: SandboxContext, command: str) -> None:
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
                        sandbox.record_package_install(pkg.split("==")[0].split(">=")[0])

        # npm install
        elif "npm install" in command_lower or "npm i " in command_lower:
            parts = command.split()
            for i, part in enumerate(parts):
                if part in ("install", "i") and i + 1 < len(parts):
                    pkg = parts[i + 1]
                    if not pkg.startswith("-"):
                        sandbox.record_package_install(f"npm:{pkg}")

        # apt install
        elif "apt install" in command_lower or "apt-get install" in command_lower:
            parts = command.split()
            for i, part in enumerate(parts):
                if part == "install" and i + 1 < len(parts):
                    pkg = parts[i + 1]
                    if not pkg.startswith("-"):
                        sandbox.record_package_install(f"apt:{pkg}")

    def _detect_file_creation(self, sandbox: SandboxContext, command: str) -> None:
        """检测并记录文件创建"""
        # 简单检测：重定向输出、touch、mkdir 等
        if ">" in command and ">>" not in command:
            # 输出重定向，提取文件路径
            parts = command.split(">")
            if len(parts) >= 2:
                filepath = parts[-1].strip().split()[0] if parts[-1].strip() else None
                if filepath:
                    sandbox.record_file_creation(filepath)

        elif command.strip().startswith("touch "):
            filepath = command.strip()[6:].split()[0]
            sandbox.record_file_creation(filepath)

        elif "mkdir " in command:
            # 提取目录名（跳过选项如 -p）
            parts = command.split()
            for i, part in enumerate(parts):
                if part == "mkdir":
                    # 找到 mkdir 后的非选项参数
                    for j in range(i + 1, len(parts)):
                        if not parts[j].startswith("-"):
                            sandbox.record_file_creation(parts[j] + "/")
                            break
                    break

    async def end_sandbox(
        self,
        sandbox_id: str,
        reason: CleanupReason = CleanupReason.USER_REQUEST,
    ) -> None:
        """结束沙箱"""
        async with self._lock:
            await self._remove_sandbox(sandbox_id, reason)

    async def _remove_sandbox(  # pylint: disable=too-many-branches
        self, sandbox_id: str, reason: CleanupReason
    ) -> None:
        """移除沙箱（内部方法，需要在锁内调用）"""
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if not sandbox:
            return

        # 保存沙箱历史（用于后续重建时提示用户）
        if sandbox.session_id:
            history = self._sandbox_history.get(sandbox.session_id)
            if history:
                history.last_sandbox_id = sandbox_id
                history.last_cleaned_at = datetime.now()
                history.cleanup_reason = reason
                history.installed_packages = sandbox.installed_packages.copy()
                history.created_files = sandbox.created_files.copy()
                history.total_commands += sandbox.command_count
            else:
                self._sandbox_history[sandbox.session_id] = SandboxHistory(
                    session_id=sandbox.session_id,
                    user_id=sandbox.user_id,
                    last_sandbox_id=sandbox_id,
                    last_cleaned_at=datetime.now(),
                    cleanup_reason=reason,
                    installed_packages=sandbox.installed_packages.copy(),
                    created_files=sandbox.created_files.copy(),
                    total_sandboxes=1,
                    total_commands=sandbox.command_count,
                )

        # 清理关联映射
        if sandbox.user_id and sandbox.user_id in self._user_sandboxes:
            self._user_sandboxes[sandbox.user_id].discard(sandbox_id)
            if not self._user_sandboxes[sandbox.user_id]:
                del self._user_sandboxes[sandbox.user_id]

        if sandbox.session_id:
            self._session_sandboxes.pop(sandbox.session_id, None)

        # 清理工作目录（在停止执行器之前，避免容器仍占用目录）
        workspace_path: str | None = None
        if sandbox.executor:
            workspace_path = getattr(sandbox.executor, "workspace_path", None)

        if self.policy.cleanup_workspace_on_sandbox_end and workspace_path:
            try:
                if await asyncio.to_thread(os.path.exists, workspace_path):
                    await asyncio.to_thread(shutil.rmtree, workspace_path)
                    logger.info(
                        "Cleaned up workspace directory for sandbox %s: %s",
                        sandbox_id,
                        workspace_path,
                    )
            except Exception as e:
                logger.warning(
                    "Failed to cleanup workspace directory for sandbox %s: %s",
                    sandbox_id,
                    e,
                )

        # 停止执行器
        if sandbox.executor:
            try:
                await sandbox.executor.stop()
            except Exception as e:
                logger.warning("Error stopping sandbox %s: %s", sandbox_id, e)

        logger.info(
            "Removed sandbox %s, reason=%s, duration=%s, commands=%d, packages=%d, files=%d",
            sandbox_id,
            reason.value,
            datetime.now() - sandbox.created_at,
            sandbox.command_count,
            len(sandbox.installed_packages),
            len(sandbox.created_files),
        )

    async def cleanup_all(self, reason: CleanupReason) -> int:
        """清理所有沙箱"""
        async with self._lock:
            sandbox_ids = list(self._sandboxes.keys())
            for sandbox_id in sandbox_ids:
                await self._remove_sandbox(sandbox_id, reason)
            return len(sandbox_ids)

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
        """检查并清理过期沙箱"""
        now = datetime.now()
        to_cleanup: list[tuple[str, CleanupReason]] = []

        async with self._lock:
            for sandbox_id, sandbox in list(self._sandboxes.items()):
                cleanup_reason = self._should_cleanup(sandbox, now)
                if cleanup_reason:
                    to_cleanup.append((sandbox_id, cleanup_reason))

            for sandbox_id, reason in to_cleanup:
                await self._remove_sandbox(sandbox_id, reason)

        if to_cleanup:
            logger.info("Cleaned up %d sandboxes", len(to_cleanup))

    def _should_cleanup(self, sandbox: SandboxContext, now: datetime) -> CleanupReason | None:
        """判断沙箱是否应该清理"""
        # 最大沙箱时长
        sandbox_duration = (now - sandbox.created_at).total_seconds()
        if sandbox_duration > self.policy.max_sandbox_duration:
            return CleanupReason.IDLE_TIMEOUT

        # 根据状态判断
        state_duration = (now - sandbox.state_changed_at).total_seconds()
        idle_duration = (now - sandbox.last_activity).total_seconds()

        if sandbox.state == SandboxRunState.COMPLETING:
            if state_duration > self.policy.completion_retain:
                return CleanupReason.TASK_COMPLETE

        elif sandbox.state == SandboxRunState.DISCONNECTED:
            if state_duration > self.policy.disconnect_timeout:
                return CleanupReason.DISCONNECT_TIMEOUT

        elif sandbox.state in (SandboxRunState.ACTIVE, SandboxRunState.IDLE):
            if idle_duration > self.policy.idle_timeout:
                return CleanupReason.IDLE_TIMEOUT

        elif sandbox.state == SandboxRunState.ERROR:
            return CleanupReason.ERROR

        return None

    # =========================================================================
    # 统计与监控
    # =========================================================================

    def get_stats(self) -> dict:
        """获取统计信息"""
        state_counts: dict[str, int] = {}
        for sandbox in self._sandboxes.values():
            state_counts[sandbox.state.value] = state_counts.get(sandbox.state.value, 0) + 1

        return {
            "total_sandboxes": len(self._sandboxes),
            "total_users": len(self._user_sandboxes),
            "state_counts": state_counts,
            "policy": {
                "idle_timeout": self.policy.idle_timeout,
                "max_sandboxes_per_user": self.policy.max_sandboxes_per_user,
                "max_total_sandboxes": self.policy.max_total_sandboxes,
            },
        }

    def get_user_sandboxes(self, user_id: str) -> list[SandboxContext]:
        """获取用户的所有沙箱"""
        sandbox_ids = self._user_sandboxes.get(user_id, set())
        return [self._sandboxes[sid] for sid in sandbox_ids if sid in self._sandboxes]

    def get_sandbox_id_by_session(self, session_id: str) -> str | None:
        """根据会话 ID 获取沙箱 ID

        Args:
            session_id: 业务会话 ID

        Returns:
            沙箱 ID，如果不存在返回 None
        """
        return self._session_sandboxes.get(session_id)

    def get_sandbox_history(self, session_id: str) -> SandboxHistory | None:
        """获取沙箱历史记录

        Args:
            session_id: 业务会话 ID

        Returns:
            沙箱历史记录，如果不存在返回 None
        """
        return self._sandbox_history.get(session_id)
