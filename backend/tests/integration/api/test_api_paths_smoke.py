"""API 路径 smoke 集成测试（使用 conftest.api_v1_url，默认 ROOT_PATH 为空）。"""

from __future__ import annotations

from httpx import AsyncClient
import pytest

from tests.conftest import api_v1_url


@pytest.mark.integration
class TestApiPathsSmoke:
    @pytest.mark.asyncio
    async def test_app_health(self, dev_client: AsyncClient) -> None:
        from libs.api.paths import service_path

        r = await dev_client.get(service_path("health"))
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_auth_me_requires_token(self, client: AsyncClient) -> None:
        r = await client.get(api_v1_url("/auth/me"))
        assert r.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_gateway_my_models_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get(api_v1_url("/gateway/my-models"))
        assert r.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_openai_models_requires_bearer(self, dev_client: AsyncClient) -> None:
        from libs.api.paths import openai_compat_base

        r = await dev_client.get(f"{openai_compat_base()}/models")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_mcp_client_config_urls(self, dev_client: AsyncClient) -> None:
        from libs.api.paths import api_v1_path

        r = await dev_client.get(api_v1_url("/mcp/client-config"))
        assert r.status_code == 200
        data = r.json()
        expected_segment = api_v1_path("mcp", "llm-server")
        url = data["mcpServers"]["ai-agent-llm"]["url"]
        assert expected_segment in url
        assert url.endswith("/llm-server")
