"""
MCP Server 初始化顺序测试

验证 FastMCP session_manager 的惰性初始化行为，
确保 initialize_mcp_servers() 正确处理初始化顺序。

背景：
FastMCP 的 session_manager 是惰性创建的，必须先调用 streamable_http_app() 才能访问。
直接访问 session_manager 会抛出 RuntimeError。

这些测试确保：
1. 我们的封装函数正确处理初始化顺序
2. 未初始化时能检测到问题
3. 初始化后可以正常访问 session_manager
"""

from unittest.mock import MagicMock, patch

import pytest

# 未安装 mcp 时跳过本模块
pytest.importorskip("mcp")


class TestMCPServerInitializationOrder:
    """MCP 服务器初始化顺序测试"""

    def test_server_not_initialized_initially(self):
        """服务器初始时应该未初始化"""
        # 重置模块状态
        from domains.agent.presentation import mcp_server_router

        # 清空缓存以测试初始状态
        original_apps = mcp_server_router._STREAMABLE_HTTP_APPS.copy()
        original_initialized = mcp_server_router._initialized

        try:
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()
            mcp_server_router._initialized = False

            # 验证初始状态
            assert not mcp_server_router.is_server_initialized("llm-server")
            assert not mcp_server_router._initialized
        finally:
            # 恢复状态
            mcp_server_router._STREAMABLE_HTTP_APPS.update(original_apps)
            mcp_server_router._initialized = original_initialized

    def test_ensure_initialized_creates_streamable_http_app(self):
        """ensure_initialized 应该创建 streamable_http_app"""
        from domains.agent.presentation import mcp_server_router

        # 保存原始状态
        original_apps = mcp_server_router._STREAMABLE_HTTP_APPS.copy()

        try:
            # 清空缓存
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()

            # Mock SERVER_MAP 中的服务器
            mock_server = MagicMock()
            mock_app = MagicMock()
            mock_server.streamable_http_app.return_value = mock_app

            with patch.dict(mcp_server_router.SERVER_MAP, {"test-server": mock_server}):
                # 调用 ensure_initialized
                mcp_server_router.ensure_initialized("test-server")

                # 验证 streamable_http_app 被调用
                mock_server.streamable_http_app.assert_called_once()

                # 验证服务器现在已初始化
                assert mcp_server_router.is_server_initialized("test-server")
        finally:
            # 恢复状态
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()
            mcp_server_router._STREAMABLE_HTTP_APPS.update(original_apps)

    def test_ensure_initialized_is_idempotent(self):
        """ensure_initialized 应该是幂等的（多次调用只初始化一次）"""
        from domains.agent.presentation import mcp_server_router

        original_apps = mcp_server_router._STREAMABLE_HTTP_APPS.copy()

        try:
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()

            mock_server = MagicMock()
            mock_app = MagicMock()
            mock_server.streamable_http_app.return_value = mock_app

            with patch.dict(mcp_server_router.SERVER_MAP, {"test-server": mock_server}):
                # 多次调用
                mcp_server_router.ensure_initialized("test-server")
                mcp_server_router.ensure_initialized("test-server")
                mcp_server_router.ensure_initialized("test-server")

                # streamable_http_app 应该只被调用一次
                mock_server.streamable_http_app.assert_called_once()
        finally:
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()
            mcp_server_router._STREAMABLE_HTTP_APPS.update(original_apps)

    @pytest.mark.asyncio
    async def test_initialize_mcp_servers_calls_streamable_http_app_before_session_manager(
        self,
    ):
        """initialize_mcp_servers 应该在访问 session_manager 之前调用 streamable_http_app"""
        from domains.agent.presentation import mcp_server_router

        original_apps = mcp_server_router._STREAMABLE_HTTP_APPS.copy()
        original_initialized = mcp_server_router._initialized

        try:
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()
            mcp_server_router._initialized = False

            # 记录调用顺序
            call_order = []

            mock_server = MagicMock()
            mock_app = MagicMock()

            def mock_streamable_http_app():
                call_order.append("streamable_http_app")
                return mock_app

            mock_server.streamable_http_app = mock_streamable_http_app

            # Mock session_manager.run() 为异步上下文管理器
            mock_session_manager = MagicMock()

            class MockRunContext:
                async def __aenter__(self):
                    call_order.append("session_manager.run")
                    return self

                async def __aexit__(self, *args):
                    pass

            mock_session_manager.run.return_value = MockRunContext()
            mock_server.session_manager = mock_session_manager

            with patch.dict(mcp_server_router.SERVER_MAP, {"test-server": mock_server}, clear=True):
                async with mcp_server_router.initialize_mcp_servers():
                    pass

            # 验证调用顺序：streamable_http_app 必须在 session_manager.run 之前
            assert call_order == ["streamable_http_app", "session_manager.run"], (
                f"调用顺序错误: {call_order}. "
                "streamable_http_app 必须在 session_manager.run 之前调用"
            )
        finally:
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()
            mcp_server_router._STREAMABLE_HTTP_APPS.update(original_apps)
            mcp_server_router._initialized = original_initialized

    @pytest.mark.asyncio
    async def test_initialize_mcp_servers_sets_initialized_flag(self):
        """initialize_mcp_servers 应该设置 _initialized 标志"""
        from domains.agent.presentation import mcp_server_router

        original_apps = mcp_server_router._STREAMABLE_HTTP_APPS.copy()
        original_initialized = mcp_server_router._initialized

        try:
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()
            mcp_server_router._initialized = False

            mock_server = MagicMock()
            mock_app = MagicMock()
            mock_server.streamable_http_app.return_value = mock_app

            mock_session_manager = MagicMock()

            class MockRunContext:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            mock_session_manager.run.return_value = MockRunContext()
            mock_server.session_manager = mock_session_manager

            with patch.dict(mcp_server_router.SERVER_MAP, {"test-server": mock_server}, clear=True):
                assert not mcp_server_router._initialized

                async with mcp_server_router.initialize_mcp_servers():
                    # 在上下文中应该已初始化
                    assert mcp_server_router._initialized

                # 退出上下文后应该重置
                assert not mcp_server_router._initialized
        finally:
            mcp_server_router._STREAMABLE_HTTP_APPS.clear()
            mcp_server_router._STREAMABLE_HTTP_APPS.update(original_apps)
            mcp_server_router._initialized = original_initialized


class TestSessionManagerLazyInitialization:
    """session_manager 惰性初始化行为测试

    这些测试验证 FastMCP 的 session_manager 惰性初始化行为，
    确保我们的代码正确处理这种情况。
    """

    def test_direct_session_manager_access_without_initialization_fails(self):
        """直接访问未初始化的 session_manager 应该失败

        这个测试记录了 FastMCP 的预期行为：
        在调用 streamable_http_app() 之前访问 session_manager 会抛出 RuntimeError
        """
        from mcp.server.fastmcp import FastMCP

        # 创建一个新的 FastMCP 实例
        server = FastMCP("test-server-for-lazy-init-test")

        # 直接访问 session_manager 应该抛出 RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            _ = server.session_manager

        assert "streamable_http_app()" in str(exc_info.value)
        assert "Session manager" in str(exc_info.value)

    def test_session_manager_accessible_after_streamable_http_app(self):
        """调用 streamable_http_app() 后应该能访问 session_manager"""
        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test-server-for-access-test")

        # 先调用 streamable_http_app()
        _ = server.streamable_http_app()

        # 现在应该能访问 session_manager
        session_manager = server.session_manager
        assert session_manager is not None
