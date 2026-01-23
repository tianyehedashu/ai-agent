"""
SessionManager 单元测试
"""

from datetime import datetime, timedelta

import pytest

from domains.agent.infrastructure.sandbox.session_manager import (
    CleanupReason,
    SessionHistory,
    SessionInfo,
    SessionManager,
    SessionPolicy,
    SessionState,
)


class TestSessionPolicy:
    """测试会话策略配置"""

    def test_default_values(self):
        """测试默认值（更友好的生产环境配置）"""
        policy = SessionPolicy()
        assert policy.idle_timeout == 7200  # 2 小时
        assert policy.disconnect_timeout == 1800  # 30 分钟
        assert policy.max_sessions_per_user == 5
        assert policy.max_total_sessions == 200
        assert policy.allow_session_reuse is True

    def test_custom_values(self):
        """测试自定义值"""
        policy = SessionPolicy(
            idle_timeout=600,
            max_sessions_per_user=5,
        )
        assert policy.idle_timeout == 600
        assert policy.max_sessions_per_user == 5


class TestSessionInfo:
    """测试会话信息"""

    def test_update_activity(self):
        """测试更新活动时间"""
        session = SessionInfo(
            session_id="test-123",
            state=SessionState.IDLE,
        )
        old_time = session.last_activity

        # 等待一小段时间
        import time

        time.sleep(0.01)
        session.update_activity()

        assert session.last_activity > old_time
        assert session.state == SessionState.ACTIVE

    def test_set_state(self):
        """测试设置状态"""
        session = SessionInfo(session_id="test-123")
        session.set_state(SessionState.COMPLETING)

        assert session.state == SessionState.COMPLETING


class TestSessionManager:
    """测试会话管理器"""

    @pytest.fixture
    def policy(self):
        """创建测试策略（短超时便于测试）"""
        return SessionPolicy(
            idle_timeout=5,
            disconnect_timeout=2,
            completion_retain=2,
            max_session_duration=10,
            max_sessions_per_user=2,
            max_total_sessions=5,
        )

    @pytest.fixture
    def manager(self, policy):
        """创建会话管理器"""
        # 重置单例
        SessionManager.reset_instance()
        return SessionManager(policy)

    def test_singleton(self):
        """测试单例模式"""
        SessionManager.reset_instance()
        m1 = SessionManager.get_instance()
        m2 = SessionManager.get_instance()
        assert m1 is m2
        SessionManager.reset_instance()

    @pytest.mark.asyncio
    async def test_start_stop(self, manager):
        """测试启动和停止"""
        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_session(self, manager):
        """集成测试：创建会话"""
        await manager.start()
        try:
            session = await manager.get_or_create_session(
                user_id="user-1",
                conversation_id="conv-1",
            )

            assert session is not None
            assert session.user_id == "user-1"
            assert session.conversation_id == "conv-1"
            assert session.state == SessionState.ACTIVE
            assert session.executor is not None
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_reuse(self, manager):
        """集成测试：会话复用"""
        await manager.start()
        try:
            # 创建第一个会话
            session1 = await manager.get_or_create_session(
                user_id="user-1",
                conversation_id="conv-1",
            )

            # 获取同一对话的会话（应该复用）
            session2 = await manager.get_or_create_session(
                user_id="user-1",
                conversation_id="conv-1",
            )

            assert session1.session_id == session2.session_id
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_session_limit(self, manager):
        """集成测试：用户会话数限制"""
        await manager.start()
        try:
            # 创建用户的多个会话
            sessions = []
            for i in range(3):
                session = await manager.get_or_create_session(
                    user_id="user-1",
                    conversation_id=f"conv-{i}",
                )
                sessions.append(session)

            # 用户应该只有 max_sessions_per_user 个会话
            user_sessions = manager.get_user_sessions("user-1")
            assert len(user_sessions) <= manager.policy.max_sessions_per_user
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_end_session(self, manager):
        """测试结束会话"""
        await manager.start()
        try:
            # 手动创建一个模拟会话（不实际创建 Docker 容器）
            session = SessionInfo(
                session_id="test-session",
                user_id="user-1",
                conversation_id="conv-1",
            )
            manager._sessions["test-session"] = session
            manager._user_sessions["user-1"] = {"test-session"}
            manager._conversation_sessions["conv-1"] = "test-session"

            # 结束会话
            await manager.end_session("test-session", CleanupReason.USER_REQUEST)

            assert "test-session" not in manager._sessions
            assert "conv-1" not in manager._conversation_sessions
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_mark_session_states(self, manager):
        """测试标记会话状态"""
        await manager.start()
        try:
            # 创建模拟会话
            session = SessionInfo(
                session_id="test-session",
                state=SessionState.ACTIVE,
            )
            manager._sessions["test-session"] = session

            # 测试各种状态转换
            await manager.mark_session_idle("test-session")
            assert session.state == SessionState.IDLE

            session.state = SessionState.ACTIVE
            await manager.mark_session_disconnected("test-session")
            assert session.state == SessionState.DISCONNECTED

            await manager.mark_session_reconnected("test-session")
            assert session.state == SessionState.ACTIVE

            await manager.mark_session_complete("test-session")
            assert session.state == SessionState.COMPLETING
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_should_cleanup_idle(self, manager):
        """测试空闲超时清理判断"""
        now = datetime.now()

        # 创建一个空闲超时的会话
        session = SessionInfo(
            session_id="test",
            state=SessionState.ACTIVE,
            last_activity=now - timedelta(seconds=manager.policy.idle_timeout + 10),
        )

        reason = manager._should_cleanup(session, now)
        assert reason == CleanupReason.IDLE_TIMEOUT

    @pytest.mark.asyncio
    async def test_should_cleanup_disconnect(self, manager):
        """测试断开超时清理判断"""
        now = datetime.now()

        # 创建一个断开超时的会话
        session = SessionInfo(
            session_id="test",
            state=SessionState.DISCONNECTED,
            state_changed_at=now - timedelta(seconds=manager.policy.disconnect_timeout + 10),
        )

        reason = manager._should_cleanup(session, now)
        assert reason == CleanupReason.DISCONNECT_TIMEOUT

    @pytest.mark.asyncio
    async def test_should_cleanup_complete(self, manager):
        """测试完成后清理判断"""
        now = datetime.now()

        # 创建一个完成后的会话
        session = SessionInfo(
            session_id="test",
            state=SessionState.COMPLETING,
            state_changed_at=now - timedelta(seconds=manager.policy.completion_retain + 10),
        )

        reason = manager._should_cleanup(session, now)
        assert reason == CleanupReason.TASK_COMPLETE

    def test_get_stats(self, manager):
        """测试获取统计信息"""
        # 添加一些模拟会话
        manager._sessions["s1"] = SessionInfo(session_id="s1", state=SessionState.ACTIVE)
        manager._sessions["s2"] = SessionInfo(session_id="s2", state=SessionState.IDLE)
        manager._sessions["s3"] = SessionInfo(session_id="s3", state=SessionState.ACTIVE)

        stats = manager.get_stats()

        assert stats["total_sessions"] == 3
        assert stats["state_counts"]["active"] == 2
        assert stats["state_counts"]["idle"] == 1

    @pytest.mark.asyncio
    async def test_session_recreation_message(self, manager):
        """测试会话重建消息生成"""
        await manager.start()
        try:
            # 创建历史记录
            history = SessionHistory(
                conversation_id="conv-1",
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
            session = SessionInfo(session_id="test", state=SessionState.ACTIVE)
            manager._sessions["test"] = session

            # 测试 pip install
            manager._detect_package_install(session, "pip install pandas==1.5.0")
            assert "pandas" in session.installed_packages

            # 测试 npm install
            manager._detect_package_install(session, "npm install express")
            assert "npm:express" in session.installed_packages

            # 测试 apt install
            manager._detect_package_install(session, "apt install git")
            assert "apt:git" in session.installed_packages
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_record_file_creation(self, manager):
        """测试文件创建检测"""
        await manager.start()
        try:
            session = SessionInfo(session_id="test", state=SessionState.ACTIVE)
            manager._sessions["test"] = session

            # 测试重定向
            manager._detect_file_creation(session, "echo 'hello' > output.txt")
            assert "output.txt" in session.created_files

            # 测试 touch
            manager._detect_file_creation(session, "touch newfile.py")
            assert "newfile.py" in session.created_files

            # 测试 mkdir
            manager._detect_file_creation(session, "mkdir -p data")
            assert "data/" in session.created_files
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_recreation_flow(self, manager):
        """集成测试：会话重建完整流程"""
        await manager.start()
        try:
            # 1. 创建第一个会话
            result1 = await manager.get_or_create_session_with_info(
                user_id="user-1",
                conversation_id="conv-1",
            )
            assert result1.is_new is True
            assert result1.is_recreated is False
            assert result1.message is None

            session1_id = result1.session.session_id

            # 2. 模拟安装包和创建文件
            result1.session.record_package_install("pandas")
            result1.session.record_file_creation("/workspace/data.csv")

            # 3. 清理会话（模拟超时）
            await manager.end_session(session1_id, CleanupReason.IDLE_TIMEOUT)

            # 4. 用户返回，重新获取会话
            result2 = await manager.get_or_create_session_with_info(
                user_id="user-1",
                conversation_id="conv-1",
            )

            # 5. 验证重建结果
            assert result2.is_new is False
            assert result2.is_recreated is True
            assert result2.previous_state is not None
            assert result2.message is not None
            assert "pandas" in result2.message
            assert "执行环境已重置" in result2.message
            assert result2.session.is_recreated is True

        finally:
            await manager.stop()
