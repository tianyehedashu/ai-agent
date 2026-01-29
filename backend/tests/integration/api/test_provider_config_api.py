"""
Provider Config API 集成测试

测试用户 LLM 提供商配置 API 端点

TDD Cycle 17-20

使用 tests/conftest.py 的 client、auth_headers fixture（与 session API 一致）。
"""

from unittest.mock import patch

from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestProviderConfigListAPI:
    """提供商配置列表 API 测试"""

    @pytest.mark.asyncio
    async def test_list_provider_configs_empty(self, client: AsyncClient, auth_headers: dict):
        """测试: 列出提供商配置 - 空列表"""
        response = await client.get(
            "/api/v1/settings/providers",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_provider_configs_unauthorized(self, client: AsyncClient):
        """测试: 未授权访问"""
        response = await client.get("/api/v1/settings/providers")

        assert response.status_code == 401


@pytest.mark.integration
class TestProviderConfigUpdateAPI:
    """提供商配置更新 API 测试"""

    @pytest.mark.asyncio
    async def test_update_provider_config_create(self, client: AsyncClient, auth_headers: dict):
        """测试: 创建提供商配置"""
        response = await client.put(
            "/api/v1/settings/providers/dashscope",
            json={
                "api_key": "sk-test-key",
                "api_base": "https://custom.api.com/v1",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "dashscope"
        assert data["api_base"] == "https://custom.api.com/v1"
        assert data["is_active"] is True
        # API Key 不应在响应中返回明文
        assert "api_key" not in data or data["api_key"] != "sk-test-key"

    @pytest.mark.asyncio
    async def test_update_provider_config_update(self, client: AsyncClient, auth_headers: dict):
        """测试: 更新已存在的提供商配置"""
        # 先创建
        await client.put(
            "/api/v1/settings/providers/openai",
            json={"api_key": "sk-old-key"},
            headers=auth_headers,
        )

        # 再更新
        response = await client.put(
            "/api/v1/settings/providers/openai",
            json={"api_key": "sk-new-key"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_update_provider_config_invalid_provider(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 无效的提供商名称"""
        response = await client.put(
            "/api/v1/settings/providers/invalid_provider",
            json={"api_key": "sk-xxx"},
            headers=auth_headers,
        )

        # 应返回 400 或 422
        assert response.status_code in [400, 422]


@pytest.mark.integration
class TestProviderConfigDeleteAPI:
    """提供商配置删除 API 测试"""

    @pytest.mark.asyncio
    async def test_delete_provider_config(self, client: AsyncClient, auth_headers: dict):
        """测试: 删除提供商配置"""
        # 先创建
        await client.put(
            "/api/v1/settings/providers/anthropic",
            json={"api_key": "sk-ant-xxx"},
            headers=auth_headers,
        )

        # 再删除
        response = await client.delete(
            "/api/v1/settings/providers/anthropic",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # 验证已删除
        list_response = await client.get(
            "/api/v1/settings/providers",
            headers=auth_headers,
        )
        providers = [p["provider"] for p in list_response.json()]
        assert "anthropic" not in providers

    @pytest.mark.asyncio
    async def test_delete_provider_config_not_found(self, client: AsyncClient, auth_headers: dict):
        """测试: 删除不存在的配置（使用有效提供商名，但用户未配置）"""
        response = await client.delete(
            "/api/v1/settings/providers/anthropic",
            headers=auth_headers,
        )

        # 应返回 404（有效提供商但无配置）
        assert response.status_code == 404


@pytest.mark.integration
class TestProviderConfigTestAPI:
    """提供商配置测试 API"""

    @pytest.mark.asyncio
    async def test_test_provider_config(self, client: AsyncClient, auth_headers: dict):
        """测试: 测试 Key 有效性"""
        # 先创建配置
        await client.put(
            "/api/v1/settings/providers/dashscope",
            json={"api_key": "sk-test-key"},
            headers=auth_headers,
        )

        # Mock LLM 调用成功
        with patch(
            "domains.agent.presentation.provider_config_router.test_provider_connection"
        ) as mock_test:
            mock_test.return_value = True

            response = await client.post(
                "/api/v1/settings/providers/dashscope/test",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
