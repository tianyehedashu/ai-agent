"""
Sandbox Executor Factory - 沙箱执行器工厂

根据配置创建正确的执行器实例
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from domains.agent.infrastructure.sandbox.executor import (
    DockerExecutor,
    LocalExecutor,
    SandboxExecutor,
    SessionDockerExecutor,
)
from libs.config.execution_config import SandboxMode

if TYPE_CHECKING:
    from libs.config.execution_config import ExecutionConfig


class ExecutorFactory:
    """
    沙箱执行器工厂

    根据 ExecutionConfig 创建正确的执行器实例
    """

    _instances: ClassVar[dict[str, SandboxExecutor]] = {}

    @classmethod
    def create(
        cls,
        config: ExecutionConfig | None = None,
        *,
        force_new: bool = False,
    ) -> SandboxExecutor:
        """
        创建沙箱执行器

        Args:
            config: 执行环境配置
            force_new: 是否强制创建新实例（不使用缓存）

        Returns:
            SandboxExecutor: 执行器实例
        """
        if config is None:
            # 默认使用本地执行器（开发环境）
            return LocalExecutor()

        mode = config.sandbox.mode
        work_dir = config.shell.work_dir
        cache_key = f"{mode.value}:{work_dir}"

        # 检查缓存
        if not force_new and cache_key in cls._instances:
            return cls._instances[cache_key]

        # 创建新实例
        executor: SandboxExecutor
        if mode == SandboxMode.DOCKER:
            docker_config = config.sandbox.docker
            if docker_config.session_enabled:
                # 会话模式：容器保持运行，状态保留
                executor = SessionDockerExecutor(
                    image=docker_config.image,
                    workspace_path=docker_config.workspace_volume,
                    container_workspace=docker_config.container_workspace,
                )
            else:
                # 无状态模式：每次命令创建新容器
                executor = DockerExecutor(
                    python_image=docker_config.image,
                    shell_image="alpine:latest",
                )
        elif mode == SandboxMode.LOCAL:
            executor = LocalExecutor(work_dir=work_dir)
        elif mode == SandboxMode.REMOTE:
            # TODO: 实现远程沙箱执行器
            raise NotImplementedError("Remote sandbox executor not implemented yet")
        else:
            # 默认使用本地执行器
            executor = LocalExecutor(work_dir=work_dir)

        # 缓存实例
        cls._instances[cache_key] = executor
        return executor

    @classmethod
    def clear_cache(cls) -> None:
        """清理执行器缓存"""
        cls._instances.clear()
