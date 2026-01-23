"""沙箱生命周期服务接口 - 领域层定义

定义沙箱生命周期管理的抽象接口，具体实现由 Infrastructure 层提供。
遵循依赖倒置原则，Application 层依赖此接口而非具体实现。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from domains.agent.domain.entities.user_quota import UserQuota


@dataclass
class SandboxInfo:
    """沙箱信息（领域类型）

    表示沙箱的当前状态信息。

    Attributes:
        sandbox_id: 沙箱唯一标识
        session_id: 关联的会话 ID
        user_id: 所属用户 ID
        is_active: 是否处于活跃状态
        created_at: 创建时间
        last_activity: 最后活动时间
        is_recreated: 是否为重建的沙箱
        recreation_message: 重建提示消息
        installed_packages: 已安装的包列表
        created_files: 已创建的文件列表
    """

    sandbox_id: str
    session_id: str
    user_id: str | None
    is_active: bool
    created_at: datetime
    last_activity: datetime
    # 重建信息
    is_recreated: bool = False
    recreation_message: str | None = None
    # 环境状态
    installed_packages: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)


@dataclass
class SandboxState:
    """沙箱状态（用于持久化）

    记录沙箱的环境状态，用于恢复或提示用户。

    Attributes:
        session_id: 关联的会话 ID
        installed_packages: 已安装的包列表
        created_files: 已创建的文件列表
        environment_variables: 环境变量
        cleanup_reason: 清理原因
        cleaned_at: 清理时间
    """

    session_id: str
    installed_packages: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    environment_variables: dict[str, str] = field(default_factory=dict)
    cleanup_reason: str | None = None
    cleaned_at: datetime | None = None


class SandboxLifecycleService(Protocol):
    """沙箱生命周期服务接口

    定义沙箱生命周期管理的抽象接口，
    具体实现由 Infrastructure 层提供。

    使用 Protocol 而非 ABC，支持结构化子类型（鸭子类型）。
    """

    async def cleanup_by_session(self, session_id: str) -> bool:
        """清理会话关联的沙箱

        当会话被删除时调用，清理关联的沙箱容器。

        Args:
            session_id: 会话 ID

        Returns:
            是否成功清理（True 表示有沙箱被清理，False 表示没有关联的沙箱）
        """
        ...

    async def ensure_available(
        self,
        session_id: str,
        user_id: str,
        quota: UserQuota,
    ) -> SandboxInfo:
        """确保会话有可用沙箱

        如果沙箱不存在则创建，如果超配额则驱逐旧的。

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            quota: 用户配额

        Returns:
            沙箱信息

        Raises:
            ResourceExhaustedError: 无法创建沙箱（资源耗尽）
        """
        ...

    async def get_by_session(self, session_id: str) -> SandboxInfo | None:
        """获取会话关联的沙箱

        Args:
            session_id: 会话 ID

        Returns:
            沙箱信息，如果不存在返回 None
        """
        ...

    async def count_user_sandboxes(self, user_id: str) -> int:
        """获取用户当前沙箱数量

        Args:
            user_id: 用户 ID

        Returns:
            用户当前拥有的沙箱数量
        """
        ...
