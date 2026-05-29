"""沙箱运行时策略（纯函数，无 IO）。

判定对话是否应预创建持久化 Docker 沙箱：
- ``wants_persistent_docker_sandbox``：仅看配置意图（docker 模式 + 启用持久沙箱）。
- ``should_pre_create_persistent_sandbox``：在配置意图之上叠加运行环境是否具备 docker CLI。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from libs.config.execution_config import ExecutionConfig


def wants_persistent_docker_sandbox(config: ExecutionConfig) -> bool:
    """配置是否要求持久化 Docker 沙箱（不考虑运行环境能力）。"""
    return config.sandbox.mode.value == "docker" and config.sandbox.docker.sandbox_enabled


def should_pre_create_persistent_sandbox(
    config: ExecutionConfig,
    *,
    docker_cli_present: bool,
) -> bool:
    """是否应在对话准备阶段预创建持久化 Docker 沙箱。"""
    return wants_persistent_docker_sandbox(config) and docker_cli_present
