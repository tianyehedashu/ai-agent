"""
Session Executor Factory - 会话执行器工厂

为 SessionManager 提供执行器创建能力，支持依赖注入和测试。
与 factory.py 的区别：
- factory.py: 面向配置的通用执行器工厂
- session_executor_factory.py: 面向 SessionManager 的会话执行器工厂（支持依赖注入）
"""

from __future__ import annotations

from typing import Protocol

from domains.agent.infrastructure.sandbox.executor import SandboxConfig, SessionDockerExecutor


class SessionExecutorFactory(Protocol):
    """
    会话执行器工厂协议

    定义创建会话执行器的接口，用于依赖注入。
    """

    def create_session_executor(
        self,
        max_idle_seconds: int,
        config: SandboxConfig | None = None,
    ) -> SessionDockerExecutor:
        """
        创建会话执行器实例

        Args:
            max_idle_seconds: 会话最大空闲时间（秒）
            config: 沙箱配置

        Returns:
            SessionDockerExecutor: 会话执行器实例
        """
        ...


class DefaultSessionExecutorFactory:
    """
    默认会话执行器工厂

    创建标准的 SessionDockerExecutor 实例。
    """

    def __init__(
        self,
        image: str = "python:3.11-slim",
        workspace_path: str | None = None,
        container_workspace: str = "/workspace",
    ) -> None:
        """
        初始化工厂

        Args:
            image: Docker 镜像
            workspace_path: 主机工作目录路径（用于持久化）
            container_workspace: 容器内工作目录
        """
        self.image = image
        self.workspace_path = workspace_path
        self.container_workspace = container_workspace

    def create_session_executor(
        self,
        max_idle_seconds: int,
        config: SandboxConfig | None = None,
    ) -> SessionDockerExecutor:
        """创建会话执行器"""
        return SessionDockerExecutor(
            image=self.image,
            workspace_path=self.workspace_path,
            container_workspace=self.container_workspace,
            max_idle_seconds=max_idle_seconds,
        )


class MockSessionExecutorFactory:
    """
    测试用模拟执行器工厂

    用于单元测试，不创建真实 Docker 容器。
    """

    def __init__(self) -> None:
        self.created_executors: list[SessionDockerExecutor] = []

    def create_session_executor(
        self,
        max_idle_seconds: int,
        config: SandboxConfig | None = None,
    ) -> SessionDockerExecutor:
        """创建模拟执行器（不启动真实容器）"""
        executor = SessionDockerExecutor(max_idle_seconds=max_idle_seconds)
        # 设置为模拟模式，不实际启动容器
        executor.configure_for_testing(
            session_id=f"mock-session-{len(self.created_executors)}",
            container_id=f"mock-container-{len(self.created_executors)}",
        )
        self.created_executors.append(executor)
        return executor
