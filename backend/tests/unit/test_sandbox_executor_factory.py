"""
SandboxExecutorFactory 单元测试

演示如何使用工厂模式进行依赖注入和测试。
"""

import pytest

from domains.agent.infrastructure.sandbox.executor import SandboxConfig
from domains.agent.infrastructure.sandbox.sandbox_executor_factory import (
    DefaultSandboxExecutorFactory,
    MockSandboxExecutorFactory,
)
from domains.agent.infrastructure.sandbox.sandbox_manager import (
    SandboxManager,
    SandboxPolicy,
    SandboxRunState,
)


class TestDefaultSandboxExecutorFactory:
    """测试默认沙箱执行器工厂"""

    def test_create_executor(self):
        """测试创建执行器"""
        factory = DefaultSandboxExecutorFactory(
            image="python:3.11-slim",
            workspace_path="/tmp/workspace",
            container_workspace="/workspace",
        )

        executor = factory.create_sandbox_executor(
            max_idle_seconds=3600,
            config=None,
        )

        assert executor is not None
        assert executor.image == "python:3.11-slim"
        assert executor.workspace_path == "/tmp/workspace"
        assert executor.max_idle_seconds == 3600

    def test_create_with_config(self):
        """测试带配置创建执行器"""
        factory = DefaultSandboxExecutorFactory()
        config = SandboxConfig(
            timeout_seconds=60,
            memory_limit_mb=512,
        )

        executor = factory.create_sandbox_executor(
            max_idle_seconds=1800,
            config=config,
        )

        assert executor is not None
        assert executor.max_idle_seconds == 1800


class TestMockSandboxExecutorFactory:
    """测试模拟沙箱执行器工厂"""

    def test_create_mock_executor(self):
        """测试创建模拟执行器"""
        factory = MockSandboxExecutorFactory()

        executor = factory.create_sandbox_executor(max_idle_seconds=3600)

        assert executor is not None
        assert executor.sandbox_id is not None
        assert executor.sandbox_id.startswith("mock-sandbox-")
        assert len(factory.created_executors) == 1

    def test_track_created_executors(self):
        """测试跟踪创建的执行器"""
        factory = MockSandboxExecutorFactory()

        executor1 = factory.create_sandbox_executor(max_idle_seconds=3600)
        executor2 = factory.create_sandbox_executor(max_idle_seconds=3600)

        assert len(factory.created_executors) == 2
        assert executor1.sandbox_id != executor2.sandbox_id


class TestSandboxManagerWithFactory:
    """测试 SandboxManager 与工厂的集成"""

    @pytest.fixture
    def mock_factory(self):
        """创建模拟工厂"""
        return MockSandboxExecutorFactory()

    @pytest.fixture
    def policy(self):
        """创建测试策略"""
        return SandboxPolicy(
            idle_timeout=5,
            max_sandboxes_per_user=2,
        )

    @pytest.fixture
    def manager_with_mock_factory(self, policy, mock_factory):
        """创建使用模拟工厂的沙箱管理器"""
        SandboxManager.reset_instance()
        return SandboxManager(policy=policy, executor_factory=mock_factory)

    @pytest.mark.asyncio
    async def test_manager_uses_injected_factory(self, manager_with_mock_factory, mock_factory):
        """测试管理器使用注入的工厂"""
        await manager_with_mock_factory.start()
        try:
            # 创建沙箱（应该使用模拟工厂，不启动真实容器）
            sandbox = await manager_with_mock_factory.get_or_create(
                user_id="test-user",
                session_id="test-session",
            )

            # 验证使用了模拟工厂
            assert len(mock_factory.created_executors) == 1
            assert sandbox.executor is not None
            assert sandbox.executor.sandbox_id.startswith("mock-sandbox-")
            assert sandbox.state == SandboxRunState.ACTIVE

        finally:
            await manager_with_mock_factory.stop()

    @pytest.mark.asyncio
    async def test_multiple_sandboxes_with_mock_factory(
        self, manager_with_mock_factory, mock_factory
    ):
        """测试使用模拟工厂创建多个沙箱"""
        await manager_with_mock_factory.start()
        try:
            # 创建多个沙箱
            sandbox1 = await manager_with_mock_factory.get_or_create(
                user_id="user-1",
                session_id="session-1",
            )
            sandbox2 = await manager_with_mock_factory.get_or_create(
                user_id="user-1",
                session_id="session-2",
            )

            # 验证工厂被调用了两次
            assert len(mock_factory.created_executors) == 2
            assert sandbox1.sandbox_id != sandbox2.sandbox_id

        finally:
            await manager_with_mock_factory.stop()

    @pytest.mark.asyncio
    async def test_manager_without_factory_uses_default(self):
        """测试未注入工厂时使用默认工厂"""
        SandboxManager.reset_instance()
        policy = SandboxPolicy(idle_timeout=5)
        manager = SandboxManager(policy=policy)  # 不注入工厂

        # 验证工厂为 None，将在首次创建沙箱时初始化
        assert manager.executor_factory is None

        SandboxManager.reset_instance()


class CustomExecutorFactory:
    """自定义执行器工厂示例"""

    def __init__(self, custom_image: str):
        self.custom_image = custom_image
        self.creation_count = 0

    def create_sandbox_executor(self, max_idle_seconds: int, config=None):
        """使用自定义镜像创建执行器"""
        from domains.agent.infrastructure.sandbox.executor import PersistentDockerExecutor

        self.creation_count += 1
        return PersistentDockerExecutor(
            image=self.custom_image,
            max_idle_seconds=max_idle_seconds,
        )


class TestCustomFactory:
    """测试自定义工厂"""

    @pytest.mark.asyncio
    async def test_custom_factory_integration(self):
        """测试自定义工厂与 SandboxManager 集成"""
        SandboxManager.reset_instance()

        # 创建自定义工厂
        custom_factory = CustomExecutorFactory(custom_image="python:3.12-alpine")
        policy = SandboxPolicy(idle_timeout=10)
        manager = SandboxManager(policy=policy, executor_factory=custom_factory)

        await manager.start()
        try:
            # 创建沙箱
            sandbox = await manager.get_or_create(
                user_id="test-user",
                session_id="test-session",
            )

            # 验证使用了自定义工厂
            assert custom_factory.creation_count == 1
            assert sandbox.executor is not None
            assert sandbox.executor.image == "python:3.12-alpine"

        finally:
            await manager.stop()
            SandboxManager.reset_instance()
