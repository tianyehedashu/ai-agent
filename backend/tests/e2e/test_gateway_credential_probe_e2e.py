"""
Gateway 凭据上游探测 E2E（真实 HTTP，不调 mock）。

前置：已启动后端（见仓库 ``scripts/run-e2e.ps1`` 或手动 uvicorn）。

认证：设置环境变量 ``E2E_USER_EMAIL`` 与 ``E2E_USER_PASSWORD``（数据库中已存在的用户）。
未设置时相关用例 ``pytest.skip``，不阻塞无密钥的 CI。

API 根地址：``E2E_API_BASE_URL``（默认 ``http://localhost:8000``）。
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from tests.e2e.config import (
    E2E_API_BASE_URL as API_BASE_URL,
)
from tests.e2e.config import (
    e2e_api_v1_path,
    e2e_service_health_path,
)


def _require_e2e_credentials() -> tuple[str, str]:
    email = os.environ.get("E2E_USER_EMAIL", "").strip()
    password = os.environ.get("E2E_USER_PASSWORD", "")
    if not email or not password:
        pytest.skip("设置 E2E_USER_EMAIL 与 E2E_USER_PASSWORD 以运行凭据探测 E2E")
    return email, password


@pytest.mark.e2e
class TestGatewayCredentialProbeE2E:
    """POST /api/v1/gateway/my-credentials/{id}/probe — Anthropic 为 unsupported，不依赖外网列表。"""

    @pytest.fixture
    def http(self) -> httpx.Client:
        return httpx.Client(base_url=API_BASE_URL, timeout=45.0)

    def test_health_reachable(self, http: httpx.Client) -> None:
        r = http.get(e2e_service_health_path())
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

    def test_my_probe_anthropic_returns_unsupported_without_upstream_list(
        self, http: httpx.Client
    ) -> None:
        email, password = _require_e2e_credentials()
        tr = http.post(
            e2e_api_v1_path("auth", "token"), json={"email": email, "password": password}
        )
        assert tr.status_code == 200, tr.text
        token = tr.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        name = f"e2e-ant-{uuid.uuid4().hex[:8]}"
        cr = http.post(
            e2e_api_v1_path("gateway", "my-credentials"),
            headers=headers,
            json={
                "provider": "anthropic",
                "name": name,
                "api_key": "sk-ant-e2e-placeholder-not-used-for-list",
                "api_base": None,
            },
        )
        assert cr.status_code == 201, cr.text
        cid = cr.json()["id"]

        pr = http.post(
            e2e_api_v1_path("gateway", "my-credentials", cid, "probe"),
            headers=headers,
            json={},
        )
        assert pr.status_code == 200, pr.text
        body = pr.json()
        assert body["support"] == "unsupported"
        assert body["upstream"] == "none"
        assert body["items"] == []
        assert body.get("message")

        dl = http.delete(e2e_api_v1_path("gateway", "my-credentials", cid), headers=headers)
        assert dl.status_code == 204
