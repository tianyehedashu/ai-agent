"""ROOT_PATH 与兼容面路由注册集成测试。"""

from __future__ import annotations

import pytest

from libs.api.paths import anthropic_compat_base, openai_compat_base, service_path


@pytest.mark.integration
def test_compat_routes_registered_on_app() -> None:
    """OpenAI / Anthropic 兼容面挂载在 api_v1_path 下。"""
    from bootstrap.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert f"{openai_compat_base()}/models" in paths
    assert f"{anthropic_compat_base()}/v1/messages" in paths


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint(dev_client) -> None:
    """默认 ROOT_PATH 下 health 在 service_path('health')。"""
    r = await dev_client.get(service_path("health"))
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_v1_redirects_to_openai_compat(dev_client) -> None:
    """ROOT_PATH 为空时，根级 /v1/models 301 至 /api/v1/openai/v1/models。"""
    r = await dev_client.get("/v1/models", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"].endswith("/api/v1/openai/v1/models")
