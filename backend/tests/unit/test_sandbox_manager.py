"""
SandboxManager 单元测试
"""

from datetime import datetime, timedelta

import pytest

from domains.agent.infrastructure.sandbox.sandbox_manager import (
    CleanupReason,
    SandboxContext,
    SandboxHistory,
    SandboxManager,
    SandboxPolicy,
    SandboxRunState,
)


class TestSandboxPolicy:
    """测试沙箱策略配置"""

    def test_default_values(self):
        """测试默认值（更友好的生产环境配置）"""
        policy = SandboxPolicy()
        assert policy.idle_timeout == 7200  # 2 小时
        assert policy.disconnect_timeout == 1800  # 30 分钟
        assert policy.max_sandboxes_per_user == 5
        assert policy.max_total_sandboxes == 200
        assert policy.allow_sandbox_reuse is True

    def test_cleanup_workspace_on_sandbox_end_default_true(self):
        """测试 cleanup_workspace_on_sandbox_end 默认为 True"""
        policy = SandboxPolicy()
        assert policy.cleanup_workspace_on_sandbox_end is True

    def test_custom_values(self):
        """测试自定义值"""
        policy = SandboxPolicy(
            idle_timeout=600,
            max_sandboxes_per_user=5,
        )
        assert policy.idle_timeout == 600
        assert policy.max_sandboxes_per_user == 5

    def test_cleanup_workspace_on_sandbox_end_custom_false(self):
        """测试 cleanup_workspace_on_sandbox_end 可设为 False"""
        policy = SandboxPolicy(cleanup_workspace_on_sandbox_end=False)
        assert policy.cleanup_workspace_on_sandbox_end is False

    def test_from_config(self):
        """测试从 SandboxPolicyConfig 构建 SandboxPolicy（单一入口）"""
        from libs.config.execution_config import SandboxPolicyConfig

        config = SandboxPolicyConfig(
            idle_timeout=3600,
            max_sandboxes_per_user=3,
            cleanup_workspace_on_sandbox_end=False,
        )
        policy = SandboxPolicy.from_config(config)
        assert policy.idle_timeout == 3600
        assert policy.max_sandboxes_per_user == 3
        assert policy.cleanup_workspace_on_sandbox_end is False
        assert policy.allow_sandbox_reuse is True  # 未覆盖的保持默认


class TestSandboxContext:
    """测试沙箱上下文信息"""

    def test_update_activity(self):
        """测试更新活动时间"""
        sandbox = SandboxContext(
            sandbox_id="test-123",
            state=SandboxRunState.IDLE,
        )
        old_time = sandbox.last_activity

        # 等待一小段时间
        import time

        time.sleep(0.01)
        sandbox.update_activity()

        assert sandbox.last_activity > old_time
        assert sandbox.state == SandboxRunState.ACTIVE

    def test_set_state(self):
        """测试设置状态"""
        sandbox = SandboxContext(sandbox_id="test-123")
        sandbox.set_state(SandboxRunState.COMPLETING)

        assert sandbox.state == SandboxRunState.COMPLETING


class TestSandboxManager:
    """测试沙箱管理器"""

    @pytest.fixture
    def policy(self):
        """创建测试策略（短超时便于测试）"""
        return SandboxPolicy(
            idle_timeout=5,
            disconnect_timeout=2,
            completion_retain=2,
            max_sandbox_duration=10,
            max_sandboxes_per_user=2,
            max_total_sandboxes=5,
        )

    @pytest.fixture
    def manager(self, policy):
        """创建沙箱管理器"""
        # 重置单例
        SandboxManager.reset_instance()
        return SandboxManager(policy)

    def test_singleton(self):
        """测试单例模式"""
        SandboxManager.reset_instance()
        m1 = SandboxManager.get_instance()
        m2 = SandboxManager.get_instance()
        assert m1 is m2
        SandboxManager.reset_instance()

    @pytest.mark.asyncio
    async def test_start_stop(self, manager):
        """测试启动和停止"""
        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_sandbox(self, manager):
        """集成测试：创建沙箱"""
        await manager.start()
        try:
            sandbox = await manager.get_or_create(
                user_id="user-1",
                session_id="session-1",
            )

            assert sandbox is not None
            assert sandbox.user_id == "user-1"
            assert sandbox.session_id == "session-1"
            assert sandbox.state == SandboxRunState.ACTIVE
            assert sandbox.executor is not None
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sandbox_reuse(self, manager):
        """集成测试：沙箱复用"""
        await manager.start()
        try:
            # 创建第一个沙箱
            sandbox1 = await manager.get_or_create(
                user_id="user-1",
                session_id="session-1",
            )

            # 获取同一会话的沙箱（应该复用）
            sandbox2 = await manager.get_or_create(
                user_id="user-1",
                session_id="session-1",
            )

            assert sandbox1.sandbox_id == sandbox2.sandbox_id
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_sandbox_limit(self, manager):
        """集成测试：用户沙箱数限制"""
        await manager.start()
        try:
            # 创建用户的多个沙箱
            sandboxes = []
            for i in range(3):
                sandbox = await manager.get_or_create(
                    user_id="user-1",
                    session_id=f"session-{i}",
                )
                sandboxes.append(sandbox)

            # 用户应该只有 max_sandboxes_per_user 个沙箱
            user_sandboxes = manager.get_user_sandboxes("user-1")
            assert len(user_sandboxes) <= manager.policy.max_sandboxes_per_user
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_end_sandbox(self, manager):
        """测试结束沙箱"""
        await manager.start()
        try:
            # 手动创建一个模拟沙箱（不实际创建 Docker 容器）
            sandbox = SandboxContext(
                sandbox_id="test-sandbox",
                user_id="user-1",
                session_id="session-1",
            )
            manager._sandboxes["test-sandbox"] = sandbox
            manager._user_sandboxes["user-1"] = {"test-sandbox"}
            manager._session_sandboxes["session-1"] = "test-sandbox"

            # 结束沙箱
            await manager.end_sandbox("test-sandbox", CleanupReason.USER_REQUEST)

            assert "test-sandbox" not in manager._sandboxes
            assert "session-1" not in manager._session_sandboxes
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_remove_sandbox_cleanup_workspace_when_enabled(self, tmp_path):
        """测试: cleanup_workspace_on_sandbox_end=True 时删除 workspace 目录"""
        # 创建带 cleanup_workspace_on_sandbox_end=True 的策略
        policy = SandboxPolicy(
            idle_timeout=5,
            disconnect_timeout=2,
            completion_retain=2,
            max_sandbox_duration=10,
            max_sandboxes_per_user=2,
            max_total_sandboxes=5,
            cleanup_workspace_on_sandbox_end=True,
        )
        SandboxManager.reset_instance()
        manager = SandboxManager(policy)

        await manager.start()
        try:
            # 创建一个临时工作目录
            workspace_dir = tmp_path / "sandbox-workspace"
            workspace_dir.mkdir()
            (workspace_dir / "test_file.txt").write_text("test content")
            assert workspace_dir.exists()

            # 创建 mock executor，设置 workspace_path
            class MockExecutor:
                def __init__(self, workspace_path: str):
                    self.workspace_path = workspace_path

                async def stop(self) -> None:
                    pass

            mock_executor = MockExecutor(str(workspace_dir))

            # 创建模拟沙箱
            sandbox = SandboxContext(
                sandbox_id="test-sandbox",
                user_id="user-1",
                session_id="session-1",
                executor=mock_executor,  # type: ignore
            )
            manager._sandboxes["test-sandbox"] = sandbox
            manager._user_sandboxes["user-1"] = {"test-sandbox"}
            manager._session_sandboxes["session-1"] = "test-sandbox"

            # 结束沙箱
            await manager.end_sandbox("test-sandbox", CleanupReason.USER_REQUEST)

            # 断言目录已被删除
            assert not workspace_dir.exists()
        finally:
            await manager.stop()
            SandboxManager.reset_instance()

    @pytest.mark.asyncio
    async def test_remove_sandbox_no_cleanup_workspace_when_disabled(self, tmp_path):
        """测试: cleanup_workspace_on_sandbox_end=False 时不删除 workspace 目录"""
        # 创建带 cleanup_workspace_on_sandbox_end=False 的策略
        policy = SandboxPolicy(
            idle_timeout=5,
            disconnect_timeout=2,
            completion_retain=2,
            max_sandbox_duration=10,
            max_sandboxes_per_user=2,
            max_total_sandboxes=5,
            cleanup_workspace_on_sandbox_end=False,
        )
        SandboxManager.reset_instance()
        manager = SandboxManager(policy)

        await manager.start()
        try:
            # 创建一个临时工作目录
            workspace_dir = tmp_path / "sandbox-workspace"
            workspace_dir.mkdir()
            (workspace_dir / "test_file.txt").write_text("test content")
            assert workspace_dir.exists()

            # 创建 mock executor，设置 workspace_path
            class MockExecutor:
                def __init__(self, workspace_path: str):
                    self.workspace_path = workspace_path

                async def stop(self) -> None:
                    pass

            mock_executor = MockExecutor(str(workspace_dir))

            # 创建模拟沙箱
            sandbox = SandboxContext(
                sandbox_id="test-sandbox",
                user_id="user-1",
                session_id="session-1",
                executor=mock_executor,  # type: ignore
            )
            manager._sandboxes["test-sandbox"] = sandbox
            manager._user_sandboxes["user-1"] = {"test-sandbox"}
            manager._session_sandboxes["session-1"] = "test-sandbox"

            # 结束沙箱
            await manager.end_sandbox("test-sandbox", CleanupReason.USER_REQUEST)

            # 断言目录仍存在
            assert workspace_dir.exists()
        finally:
            await manager.stop()
            SandboxManager.reset_instance()

    @pytest.mark.asyncio
    async def test_remove_sandbox_no_cleanup_when_workspace_path_none(self, policy):
        """测试: workspace_path 为 None 时不尝试删除，不抛异常"""
        # 使用默认策略（cleanup_workspace_on_sandbox_end=True）
        policy_with_cleanup = SandboxPolicy(
            idle_timeout=5,
            disconnect_timeout=2,
            completion_retain=2,
            max_sandbox_duration=10,
            max_sandboxes_per_user=2,
            max_total_sandboxes=5,
            cleanup_workspace_on_sandbox_end=True,
        )
        SandboxManager.reset_instance()
        manager = SandboxManager(policy_with_cleanup)

        await manager.start()
        try:
            # 创建 mock executor，workspace_path 为 None
            class MockExecutor:
                def __init__(self):
                    self.workspace_path = None

                async def stop(self) -> None:
                    pass

            mock_executor = MockExecutor()

            # 创建模拟沙箱
            sandbox = SandboxContext(
                sandbox_id="test-sandbox",
                user_id="user-1",
                session_id="session-1",
                executor=mock_executor,  # type: ignore
            )
            manager._sandboxes["test-sandbox"] = sandbox
            manager._user_sandboxes["user-1"] = {"test-sandbox"}
            manager._session_sandboxes["session-1"] = "test-sandbox"

            # 结束沙箱 - 不应抛异常
            await manager.end_sandbox("test-sandbox", CleanupReason.USER_REQUEST)

            # 沙箱应被正常移除
            assert "test-sandbox" not in manager._sandboxes
        finally:
            await manager.stop()
            SandboxManager.reset_instance()

    @pytest.mark.asyncio
    async def test_mark_sandbox_states(self, manager):
        """测试标记沙箱状态"""
        await manager.start()
        try:
            # 创建模拟沙箱
            sandbox = SandboxContext(
                sandbox_id="test-sandbox",
                state=SandboxRunState.ACTIVE,
            )
            manager._sandboxes["test-sandbox"] = sandbox

            # 测试各种状态转换
            await manager.mark_sandbox_idle("test-sandbox")
            assert sandbox.state == SandboxRunState.IDLE

            sandbox.state = SandboxRunState.ACTIVE
            await manager.mark_sandbox_disconnected("test-sandbox")
            assert sandbox.state == SandboxRunState.DISCONNECTED

            await manager.mark_sandbox_reconnected("test-sandbox")
            assert sandbox.state == SandboxRunState.ACTIVE

            await manager.mark_sandbox_complete("test-sandbox")
            assert sandbox.state == SandboxRunState.COMPLETING
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_should_cleanup_idle(self, manager):
        """测试空闲超时清理判断"""
        now = datetime.now()

        # 创建一个空闲超时的沙箱
        sandbox = SandboxContext(
            sandbox_id="test",
            state=SandboxRunState.ACTIVE,
            last_activity=now - timedelta(seconds=manager.policy.idle_timeout + 10),
        )

        reason = manager._should_cleanup(sandbox, now)
        assert reason == CleanupReason.IDLE_TIMEOUT

    @pytest.mark.asyncio
    async def test_should_cleanup_disconnect(self, manager):
        """测试断开超时清理判断"""
        now = datetime.now()

        # 创建一个断开超时的沙箱
        sandbox = SandboxContext(
            sandbox_id="test",
            state=SandboxRunState.DISCONNECTED,
            state_changed_at=now - timedelta(seconds=manager.policy.disconnect_timeout + 10),
        )

        reason = manager._should_cleanup(sandbox, now)
        assert reason == CleanupReason.DISCONNECT_TIMEOUT

    @pytest.mark.asyncio
    async def test_should_cleanup_complete(self, manager):
        """测试完成后清理判断"""
        now = datetime.now()

        # 创建一个完成后的沙箱
        sandbox = SandboxContext(
            sandbox_id="test",
            state=SandboxRunState.COMPLETING,
            state_changed_at=now - timedelta(seconds=manager.policy.completion_retain + 10),
        )

        reason = manager._should_cleanup(sandbox, now)
        assert reason == CleanupReason.TASK_COMPLETE

    def test_get_stats(self, manager):
        """测试获取统计信息"""
        # 添加一些模拟沙箱
        manager._sandboxes["s1"] = SandboxContext(sandbox_id="s1", state=SandboxRunState.ACTIVE)
        manager._sandboxes["s2"] = SandboxContext(sandbox_id="s2", state=SandboxRunState.IDLE)
        manager._sandboxes["s3"] = SandboxContext(sandbox_id="s3", state=SandboxRunState.ACTIVE)

        stats = manager.get_stats()

        assert stats["total_sandboxes"] == 3
        assert stats["state_counts"]["active"] == 2
        assert stats["state_counts"]["idle"] == 1

    @pytest.mark.asyncio
    async def test_sandbox_recreation_message(self, manager):
        """测试沙箱重建消息生成"""
        await manager.start()
        try:
            # 创建历史记录
            history = SandboxHistory(
                session_id="session-1",
                cleanup_reason=CleanupReason.IDLE_TIMEOUT,
                installed_packages=["pandas", "numpy", "requests"],
                created_files=["/workspace/data.csv", "/workspace/output.txt"],
            )

            message = manager._generate_recreation_message(history)

            assert "执行环境已重置" in message
            assert "长时间未活动" in message
            assert "pandas" in message
            assert "2 个" in message  # 文件数量
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_record_package_install(self, manager):
        """测试包安装检测"""
        await manager.start()
        try:
            sandbox = SandboxContext(sandbox_id="test", state=SandboxRunState.ACTIVE)
            manager._sandboxes["test"] = sandbox

            # 测试 pip install
            manager._detect_package_install(sandbox, "pip install pandas==1.5.0")
            assert "pandas" in sandbox.installed_packages

            # 测试 npm install
            manager._detect_package_install(sandbox, "npm install express")
            assert "npm:express" in sandbox.installed_packages

            # 测试 apt install
            manager._detect_package_install(sandbox, "apt install git")
            assert "apt:git" in sandbox.installed_packages
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_record_file_creation(self, manager):
        """测试文件创建检测"""
        await manager.start()
        try:
            sandbox = SandboxContext(sandbox_id="test", state=SandboxRunState.ACTIVE)
            manager._sandboxes["test"] = sandbox

            # 测试重定向
            manager._detect_file_creation(sandbox, "echo 'hello' > output.txt")
            assert "output.txt" in sandbox.created_files

            # 测试 touch
            manager._detect_file_creation(sandbox, "touch newfile.py")
            assert "newfile.py" in sandbox.created_files

            # 测试 mkdir
            manager._detect_file_creation(sandbox, "mkdir -p data")
            assert "data/" in sandbox.created_files
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sandbox_recreation_flow(self, manager):
        """集成测试：沙箱重建完整流程"""
        await manager.start()
        try:
            # 1. 创建第一个沙箱
            result1 = await manager.get_or_create_with_info(
                user_id="user-1",
                session_id="session-1",
            )
            assert result1.is_new is True
            assert result1.is_recreated is False
            assert result1.message is None

            sandbox1_id = result1.sandbox.sandbox_id

            # 2. 模拟安装包和创建文件
            result1.sandbox.record_package_install("pandas")
            result1.sandbox.record_file_creation("/workspace/data.csv")

            # 3. 清理沙箱（模拟超时）
            await manager.end_sandbox(sandbox1_id, CleanupReason.IDLE_TIMEOUT)

            # 4. 用户返回，重新获取沙箱
            result2 = await manager.get_or_create_with_info(
                user_id="user-1",
                session_id="session-1",
            )

            # 5. 验证重建结果
            assert result2.is_new is False
            assert result2.is_recreated is True
            assert result2.previous_state is not None
            assert result2.message is not None
            assert "pandas" in result2.message
            assert "执行环境已重置" in result2.message
            assert result2.sandbox.is_recreated is True

        finally:
            await manager.stop()
