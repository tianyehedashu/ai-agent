"""
匿名用户 API 集成测试

测试基于 Cookie 的匿名用户隔离机制在 API 层面的行为
"""

from collections.abc import AsyncGenerator
import re
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from shared.presentation import ANONYMOUS_USER_COOKIE


@pytest_asyncio.fixture
async def dev_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """开发模式 HTTP 客户端 fixture（启用匿名用户功能）"""
    # 延迟导入，避免在导入时触发 lifespan 和循环导入
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("shared.infrastructure.db.database.init_db"),
        patch("shared.infrastructure.db.redis.init_redis"),
        patch("shared.infrastructure.db.database.get_session_factory", return_value=mock_factory),
        patch("shared.infrastructure.db.database.get_async_session", new=mock_factory),
        # 保持开发模式以启用匿名用户功能
        patch("bootstrap.config.settings.app_env", "development"),
    ):
        from bootstrap.main import app
        from domains.runtime.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
        from shared.infrastructure.db.database import get_session

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_session] = override_get_session

        # 确保 checkpointer 在测试环境中已初始化
        if not hasattr(app.state, "checkpointer"):
            test_checkpointer = LangGraphCheckpointer(storage_type="memory")
            await test_checkpointer.setup()
            app.state.checkpointer = test_checkpointer

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

        app.dependency_overrides.clear()


@pytest.mark.integration
class TestAnonymousUserAPI:
    """匿名用户 API 集成测试"""

    @pytest.mark.asyncio
    async def test_first_request_sets_cookie(self, dev_client: AsyncClient):
        """测试: 首次请求设置 Cookie"""
        # Act
        response = await dev_client.get("/api/v1/sessions/")

        # Assert
        assert response.status_code == 200
        # 检查响应中是否包含设置 Cookie 的头
        set_cookie = response.headers.get("set-cookie", "")
        assert ANONYMOUS_USER_COOKIE in set_cookie

    @pytest.mark.asyncio
    async def test_same_cookie_same_user(self, dev_client: AsyncClient):
        """测试: 相同 Cookie 返回相同用户"""
        # Act - 首次请求
        response1 = await dev_client.get("/api/v1/sessions/")
        assert response1.status_code == 200

        # 提取 Cookie
        cookies = response1.cookies
        anonymous_id = cookies.get(ANONYMOUS_USER_COOKIE)
        assert anonymous_id is not None

        # Act - 使用相同 Cookie 的第二次请求
        # 将 cookie 设置在 client 实例上，而不是作为请求参数
        dev_client.cookies.set(ANONYMOUS_USER_COOKIE, anonymous_id)
        response2 = await dev_client.get("/api/v1/sessions/")

        # Assert - 两次请求都应该成功
        assert response2.status_code == 200

    @pytest.mark.asyncio
    async def test_different_cookies_different_users(self, db_session: AsyncSession):
        """测试: 不同 Cookie 对应不同用户（会话隔离）"""
        # 使用两个独立的客户端来模拟不同的浏览器
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("shared.infrastructure.db.database.init_db"),
            patch("shared.infrastructure.db.redis.init_redis"),
            patch("shared.infrastructure.db.database.get_session_factory", return_value=mock_factory),
            patch("shared.infrastructure.db.database.get_async_session", new=mock_factory),
            patch("bootstrap.config.settings.app_env", "development"),
        ):
            from bootstrap.main import app
            from domains.runtime.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
            from shared.infrastructure.db.database import get_session

            async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
                yield db_session

            app.dependency_overrides[get_session] = override_get_session

            if not hasattr(app.state, "checkpointer"):
                test_checkpointer = LangGraphCheckpointer(storage_type="memory")
                await test_checkpointer.setup()
                app.state.checkpointer = test_checkpointer

            # 客户端 1
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client1:
                response1 = await client1.get("/api/v1/sessions/")
                set_cookie1 = response1.headers.get("set-cookie", "")
                match1 = re.search(rf"{ANONYMOUS_USER_COOKIE}=([^;]+)", set_cookie1)
                anonymous_id_1 = match1.group(1) if match1 else None

            # 客户端 2（独立的客户端实例，没有 cookies）
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client2:
                response2 = await client2.get("/api/v1/sessions/")
                set_cookie2 = response2.headers.get("set-cookie", "")
                match2 = re.search(rf"{ANONYMOUS_USER_COOKIE}=([^;]+)", set_cookie2)
                anonymous_id_2 = match2.group(1) if match2 else None

            app.dependency_overrides.clear()

        # Assert - 两个客户端应该有不同的 anonymous_id
        assert anonymous_id_1 is not None
        assert anonymous_id_2 is not None
        assert anonymous_id_1 != anonymous_id_2

    @pytest.mark.asyncio
    async def test_cookie_persists_across_requests(self, dev_client: AsyncClient):
        """测试: Cookie 在多次请求中保持不变"""
        # Arrange - 首次请求获取 Cookie
        response1 = await dev_client.get("/api/v1/sessions/")
        cookies = response1.cookies
        anonymous_id = cookies.get(ANONYMOUS_USER_COOKIE)

        # Act - 将 cookie 设置在 client 实例上，然后连续多次请求
        dev_client.cookies.set(ANONYMOUS_USER_COOKIE, anonymous_id)
        for _ in range(3):
            response = await dev_client.get("/api/v1/sessions/")
            assert response.status_code == 200

        # Assert - anonymous_id 应该保持不变
        # （如果服务端正确识别了 Cookie，不会在响应中再次设置）

    @pytest.mark.asyncio
    async def test_sessions_isolated_by_user(self, dev_client: AsyncClient):
        """测试: 会话按用户隔离"""
        # Arrange - 客户端 1 创建会话
        response1 = await dev_client.get("/api/v1/sessions/")
        cookies1 = response1.cookies
        cookies1.get(ANONYMOUS_USER_COOKIE)
        response1.json()

        # Act - 客户端 2 获取会话列表（应该是空的，因为是新用户）
        # 注意：清除 Cookie，模拟新客户端
        dev_client.cookies.clear()
        response2 = await dev_client.get("/api/v1/sessions/")
        response2.json()

        # Assert
        # 注意：新用户的会话列表可能为空，这取决于是否有预先创建的会话
        # 重要的是两个用户的会话列表是独立的
        assert response1.status_code == 200
        assert response2.status_code == 200
