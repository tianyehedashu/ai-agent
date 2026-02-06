"""
Sandbox - 沙箱执行系统

提供安全的代码执行环境：
- DockerExecutor: Docker 容器隔离执行（无状态，每次新容器）
- PersistentDockerExecutor: 持久化 Docker 执行器（状态保持，支持持久化卷）
- LocalExecutor: 本地直接执行（仅开发环境）
- ExecutorFactory: 根据配置创建正确的执行器
- SandboxManager: 沙箱生命周期管理
- SandboxExecutorFactory: 沙箱执行器工厂协议（依赖注入）
- DefaultSandboxExecutorFactory: 默认沙箱执行器工厂
- MockSandboxExecutorFactory: 测试用模拟工厂
- SandboxLifecycleAdapter: 沙箱生命周期适配器（实现领域服务接口）
"""

from domains.agent.infrastructure.sandbox.executor import (
    DockerExecutor,
    ExecutionResult,
    LocalExecutor,
    PersistentDockerExecutor,
    SandboxConfig,
    SandboxExecutor,
)
from domains.agent.infrastructure.sandbox.factory import ExecutorFactory
from domains.agent.infrastructure.sandbox.lifecycle_adapter import (
    SandboxLifecycleAdapter,
)
from domains.agent.infrastructure.sandbox.sandbox_executor_factory import (
    DefaultSandboxExecutorFactory,
    MockSandboxExecutorFactory,
    SandboxExecutorFactory,
)
from domains.agent.infrastructure.sandbox.sandbox_manager import (
    CleanupReason,
    SandboxContext,
    SandboxCreationResult,
    SandboxHistory,
    SandboxManager,
    SandboxPolicy,
    SandboxRunState,
)

__all__ = [
    "CleanupReason",
    "DefaultSandboxExecutorFactory",
    "DockerExecutor",
    "ExecutionResult",
    "ExecutorFactory",
    "LocalExecutor",
    "MockSandboxExecutorFactory",
    "PersistentDockerExecutor",
    "SandboxConfig",
    "SandboxContext",
    "SandboxCreationResult",
    "SandboxExecutor",
    "SandboxExecutorFactory",
    "SandboxHistory",
    "SandboxLifecycleAdapter",
    "SandboxManager",
    "SandboxPolicy",
    "SandboxRunState",
]
