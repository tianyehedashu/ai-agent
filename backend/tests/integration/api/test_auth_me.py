"""
认证端点集成测试。使用 tests/conftest.py 的 dev_client fixture。

测试 /api/v1/auth/me 端点的基本功能，确保 JWT 配置正确。
"""

import pytest

from bootstrap.config import settings


@pytest.mark.integration
class TestAuthMe:
    """认证端点测试"""

    @pytest.mark.asyncio
    async def test_auth_me_requires_authentication(self, dev_client):
        """测试: 未认证访问 /api/v1/auth/me 返回 401"""
        from httpx import AsyncClient

        client: AsyncClient = dev_client
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_config_correct(self):
        """测试: JWT 配置正确，jwt_secret_key 可以从 jwt_secret 获取"""
        assert settings.jwt_secret is not None
        assert settings.jwt_secret_key is not None
        assert (
            settings.jwt_secret_key != "jwt-secret-change-in-production"
            or settings.jwt_secret.get_secret_value() != "jwt-secret-change-in-production"
        )
        assert settings.jwt_secret_key == settings.jwt_secret.get_secret_value()
