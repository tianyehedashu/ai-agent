"""
认证端点集成测试

测试 /api/v1/auth/me 端点的基本功能，确保：
1. 开发环境下支持匿名用户
2. JWT 配置正确
3. 不会因为配置问题导致 401 错误
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.identity.presentation.deps import ANONYMOUS_USER_COOKIE


@pytest_asyncio.fixture
async def dev_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """开发模式 HTTP 客户端 fixture"""
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("libs.db.database.init_db"),
        patch("libs.db.redis.init_redis"),
        patch("libs.db.database.get_session_factory", return_value=mock_factory),
        patch("libs.db.database.get_async_session", new=mock_factory),
        patch("bootstrap.config.settings.app_env", "development"),
    ):
        from bootstrap.main import app
        from domains.agent.infrastructure.engine.langgraph_checkpointer import (
            LangGraphCheckpointer,
        )
        from libs.db.database import get_session

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_session] = override_get_session

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
class TestAuthMe:
    """认证端点测试"""

    @pytest.mark.asyncio
    async def test_auth_me_with_anonymous_user(self, dev_client: AsyncClient):
        """测试: 开发环境下匿名用户可以访问 /api/v1/auth/me"""
        # Act
        response = await dev_client.get("/api/v1/auth/me")

        # Assert
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert "is_anonymous" in data
        assert data["is_anonymous"] is True

    @pytest.mark.asyncio
    async def test_auth_me_sets_cookie(self, dev_client: AsyncClient):
        """测试: /api/v1/auth/me 设置匿名用户 Cookie"""
        # Act
        response = await dev_client.get("/api/v1/auth/me")

        # Assert
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert ANONYMOUS_USER_COOKIE in set_cookie

    @pytest.mark.asyncio
    async def test_jwt_config_correct(self):
        """测试: JWT 配置正确，jwt_secret_key 可以从 jwt_secret 获取"""
        # Assert
        assert settings.jwt_secret is not None
        assert settings.jwt_secret_key is not None
        assert settings.jwt_secret_key != "jwt-secret-change-in-production" or settings.jwt_secret.get_secret_value() != "jwt-secret-change-in-production"
        # jwt_secret_key 应该等于 jwt_secret 的值（如果 JWT_SECRET_KEY 未设置）
        assert settings.jwt_secret_key == settings.jwt_secret.get_secret_value()
