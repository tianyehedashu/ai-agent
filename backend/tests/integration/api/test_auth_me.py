"""
认证端点集成测试。使用 tests/conftest.py 的 dev_client fixture。

测试 /api/v1/auth/me 端点的基本功能，确保：
1. 开发环境下支持匿名用户
2. JWT 配置正确
3. 不会因为配置问题导致 401 错误
"""

from httpx import AsyncClient
import pytest

from bootstrap.config import settings
from domains.identity.presentation.deps import ANONYMOUS_USER_COOKIE


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
