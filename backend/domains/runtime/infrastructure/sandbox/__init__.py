"""
Sandbox - 沙箱执行系统

提供安全的代码执行环境：
- DockerExecutor: Docker 容器隔离执行（无状态，每次新容器）
- SessionDockerExecutor: 会话级容器（状态保持，支持持久化卷）
- LocalExecutor: 本地直接执行（仅开发环境）
- ExecutorFactory: 根据配置创建正确的执行器
- SessionManager: 会话生命周期管理
- SessionExecutorFactory: 会话执行器工厂协议（依赖注入）
- DefaultSessionExecutorFactory: 默认会话执行器工厂
- MockSessionExecutorFactory: 测试用模拟工厂
"""

from domains.runtime.infrastructure.sandbox.executor import (
    DockerExecutor,
    ExecutionResult,
    LocalExecutor,
    SandboxConfig,
    SandboxExecutor,
    SessionDockerExecutor,
)
from domains.runtime.infrastructure.sandbox.factory import ExecutorFactory
from domains.runtime.infrastructure.sandbox.session_executor_factory import (
    DefaultSessionExecutorFactory,
    MockSessionExecutorFactory,
    SessionExecutorFactory,
)
from domains.runtime.infrastructure.sandbox.session_manager import (
    CleanupReason,
    SessionHistory,
    SessionInfo,
    SessionManager,
    SessionPolicy,
    SessionRecreationResult,
    SessionState,
)

__all__ = [
    "CleanupReason",
    "DefaultSessionExecutorFactory",
    "DockerExecutor",
    "ExecutionResult",
    "ExecutorFactory",
    "LocalExecutor",
    "MockSessionExecutorFactory",
    "SandboxConfig",
    "SandboxExecutor",
    "SessionDockerExecutor",
    "SessionExecutorFactory",
    "SessionHistory",
    "SessionInfo",
    "SessionManager",
    "SessionPolicy",
    "SessionRecreationResult",
    "SessionState",
]
