"""
SessionExecutorFactory 单元测试

演示如何使用工厂模式进行依赖注入和测试。
"""

import pytest

from domains.agent.infrastructure.sandbox.executor import SandboxConfig
from domains.agent.infrastructure.sandbox.session_executor_factory import (
    DefaultSessionExecutorFactory,
    MockSessionExecutorFactory,
)
from domains.agent.infrastructure.sandbox.session_manager import (
    SessionManager,
    SessionPolicy,
    SessionState,
)


class TestDefaultSessionExecutorFactory:
    """测试默认会话执行器工厂"""

    def test_create_executor(self):
        """测试创建执行器"""
        factory = DefaultSessionExecutorFactory(
            image="python:3.11-slim",
            workspace_path="/tmp/workspace",
            container_workspace="/workspace",
        )

        executor = factory.create_session_executor(
            max_idle_seconds=3600,
            config=None,
        )

        assert executor is not None
        assert executor.image == "python:3.11-slim"
        assert executor.workspace_path == "/tmp/workspace"
        assert executor.max_idle_seconds == 3600

    def test_create_with_config(self):
        """测试带配置创建执行器"""
        factory = DefaultSessionExecutorFactory()
        config = SandboxConfig(
            timeout_seconds=60,
            memory_limit_mb=512,
        )

        executor = factory.create_session_executor(
            max_idle_seconds=1800,
            config=config,
        )

        assert executor is not None
        assert executor.max_idle_seconds == 1800


class TestMockSessionExecutorFactory:
    """测试模拟会话执行器工厂"""

    def test_create_mock_executor(self):
        """测试创建模拟执行器"""
        factory = MockSessionExecutorFactory()

        executor = factory.create_session_executor(max_idle_seconds=3600)

        assert executor is not None
        assert executor.session_id is not None
        assert executor.session_id.startswith("mock-session-")
        assert len(factory.created_executors) == 1

    def test_track_created_executors(self):
        """测试跟踪创建的执行器"""
        factory = MockSessionExecutorFactory()

        executor1 = factory.create_session_executor(max_idle_seconds=3600)
        executor2 = factory.create_session_executor(max_idle_seconds=3600)

        assert len(factory.created_executors) == 2
        assert executor1.session_id != executor2.session_id


class TestSessionManagerWithFactory:
    """测试 SessionManager 与工厂的集成"""

    @pytest.fixture
    def mock_factory(self):
        """创建模拟工厂"""
        return MockSessionExecutorFactory()

    @pytest.fixture
    def policy(self):
        """创建测试策略"""
        return SessionPolicy(
            idle_timeout=5,
            max_sessions_per_user=2,
        )

    @pytest.fixture
    def manager_with_mock_factory(self, policy, mock_factory):
        """创建使用模拟工厂的会话管理器"""
        SessionManager.reset_instance()
        return SessionManager(policy=policy, executor_factory=mock_factory)

    @pytest.mark.asyncio
    async def test_manager_uses_injected_factory(self, manager_with_mock_factory, mock_factory):
        """测试管理器使用注入的工厂"""
        await manager_with_mock_factory.start()
        try:
            # 创建会话（应该使用模拟工厂，不启动真实容器）
            session = await manager_with_mock_factory.get_or_create_session(
                user_id="test-user",
                conversation_id="test-conv",
            )

            # 验证使用了模拟工厂
            assert len(mock_factory.created_executors) == 1
            assert session.executor is not None
            assert session.executor.session_id.startswith("mock-session-")
            assert session.state == SessionState.ACTIVE

        finally:
            await manager_with_mock_factory.stop()

    @pytest.mark.asyncio
    async def test_multiple_sessions_with_mock_factory(
        self, manager_with_mock_factory, mock_factory
    ):
        """测试使用模拟工厂创建多个会话"""
        await manager_with_mock_factory.start()
        try:
            # 创建多个会话
            session1 = await manager_with_mock_factory.get_or_create_session(
                user_id="user-1",
                conversation_id="conv-1",
            )
            session2 = await manager_with_mock_factory.get_or_create_session(
                user_id="user-1",
                conversation_id="conv-2",
            )

            # 验证工厂被调用了两次
            assert len(mock_factory.created_executors) == 2
            assert session1.session_id != session2.session_id

        finally:
            await manager_with_mock_factory.stop()

    @pytest.mark.asyncio
    async def test_manager_without_factory_uses_default(self):
        """测试未注入工厂时使用默认工厂"""
        SessionManager.reset_instance()
        policy = SessionPolicy(idle_timeout=5)
        manager = SessionManager(policy=policy)  # 不注入工厂

        # 验证工厂为 None，将在首次创建会话时初始化
        assert manager.executor_factory is None

        SessionManager.reset_instance()


class CustomExecutorFactory:
    """自定义执行器工厂示例"""

    def __init__(self, custom_image: str):
        self.custom_image = custom_image
        self.creation_count = 0

    def create_session_executor(self, max_idle_seconds: int, config=None):
        """使用自定义镜像创建执行器"""
        from domains.agent.infrastructure.sandbox.executor import SessionDockerExecutor

        self.creation_count += 1
        return SessionDockerExecutor(
            image=self.custom_image,
            max_idle_seconds=max_idle_seconds,
        )


class TestCustomFactory:
    """测试自定义工厂"""

    @pytest.mark.asyncio
    async def test_custom_factory_integration(self):
        """测试自定义工厂与 SessionManager 集成"""
        SessionManager.reset_instance()

        # 创建自定义工厂
        custom_factory = CustomExecutorFactory(custom_image="python:3.12-alpine")
        policy = SessionPolicy(idle_timeout=10)
        manager = SessionManager(policy=policy, executor_factory=custom_factory)

        await manager.start()
        try:
            # 创建会话
            session = await manager.get_or_create_session(
                user_id="test-user",
                conversation_id="test-conv",
            )

            # 验证使用了自定义工厂
            assert custom_factory.creation_count == 1
            assert session.executor is not None
            assert session.executor.image == "python:3.12-alpine"

        finally:
            await manager.stop()
            SessionManager.reset_instance()
