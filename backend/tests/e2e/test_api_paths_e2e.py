"""
API 路径 E2E（真实 HTTP，验证服务级前缀与兼容面）。

前置：后端已启动（``scripts/run-e2e.ps1`` 或 uvicorn）。
``ROOT_PATH`` / ``E2E_ROOT_PATH`` 需与后端进程一致（默认空）。
"""

from __future__ import annotations

import httpx
import pytest

from tests.e2e.config import (
    E2E_API_BASE_URL,
    e2e_anthropic_messages_path,
    e2e_openai_models_path,
    e2e_service_health_path,
)


@pytest.mark.e2e
class TestApiPathsE2E:
    def test_service_health(self) -> None:
        with httpx.Client(base_url=E2E_API_BASE_URL, timeout=10.0) as client:
            r = client.get(e2e_service_health_path())
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "healthy"

    def test_openai_models_requires_auth(self) -> None:
        with httpx.Client(base_url=E2E_API_BASE_URL, timeout=10.0) as client:
            r = client.get(e2e_openai_models_path())
        assert r.status_code == 401, r.text

    def test_legacy_v1_models_redirects_when_no_root_path(self) -> None:
        """ROOT_PATH 为空时 /v1/models 应 301 到新 OpenAI 兼容面。"""
        from bootstrap.config import settings

        if settings.root_path.strip("/"):
            pytest.skip("legacy /v1 重定向仅在 ROOT_PATH 为空时注册")
        with httpx.Client(base_url=E2E_API_BASE_URL, timeout=10.0) as client:
            r = client.get("/v1/models", follow_redirects=False)
        assert r.status_code == 301, r.text
        assert r.headers["location"].endswith("/api/v1/openai/v1/models")

    def test_mcp_client_config_contains_api_path(self) -> None:
        from libs.api.paths import api_v1_path

        with httpx.Client(base_url=E2E_API_BASE_URL, timeout=10.0) as client:
            r = client.get(api_v1_path("mcp", "client-config"))
        assert r.status_code == 200, r.text
        url = r.json()["mcpServers"]["ai-agent-llm"]["url"]
        assert api_v1_path("mcp", "llm-server") in url

    def test_anthropic_messages_requires_auth(self) -> None:
        with httpx.Client(base_url=E2E_API_BASE_URL, timeout=10.0) as client:
            r = client.post(
                e2e_anthropic_messages_path(),
                json={
                    "model": "claude-test",
                    "max_tokens": 8,
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
        assert r.status_code == 401, r.text
