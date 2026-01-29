"""
API Key API 集成测试

测试 API Key 管理 API 端点。使用 tests/conftest.py 的 client fixture。
"""

from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestApiKeyAPI:
    """API Key API 测试"""

    @pytest.mark.asyncio
    async def test_scopes_list(self, client: AsyncClient):
        """测试: 获取作用域列表（不需要权限）"""
        response = await client.get("/api/v1/api-keys/scopes/list")

        assert response.status_code == 200
        scopes = response.json()
        assert isinstance(scopes, list)
        assert "agent:read" in scopes
        assert "session:read" in scopes

    @pytest.mark.asyncio
    async def test_scopes_groups(self, client: AsyncClient):
        """测试: 获取作用域分组（不需要权限）"""
        response = await client.get("/api/v1/api-keys/scopes/groups")

        assert response.status_code == 200
        groups = response.json()
        assert "read_only" in groups
        assert "full_access" in groups
        assert isinstance(groups["read_only"], list)


@pytest.mark.integration
class TestApiKeyAuthFlow:
    """API Key 认证流程测试"""

    @pytest.mark.asyncio
    async def test_api_key_endpoints_exist(self, client: AsyncClient):
        """测试: API Key 端点存在"""
        # 验证 API Key 作用域端点存在
        response = await client.get("/api/v1/api-keys/scopes/list")
        assert response.status_code == 200
