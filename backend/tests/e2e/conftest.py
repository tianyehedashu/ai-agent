"""E2E 共享 fixture（真实 HTTP，依赖 localhost:8000 与可选登录凭据）。"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import os

import httpx
import pytest

from tests.e2e.config import E2E_API_BASE_URL, e2e_api_v1_path

# .env 由 tests.e2e.config 加载；勿在此重复 load_dotenv，以免 ROOT_PATH 与 get_settings 缓存不一致


def _e2e_backend_reachable() -> bool:
    try:
        from tests.e2e.config import E2E_API_BASE_URL, e2e_service_health_path

        with httpx.Client(base_url=E2E_API_BASE_URL, timeout=3.0) as client:
            return client.get(e2e_service_health_path()).status_code == 200
    except Exception:
        return False


def pytest_collection_modifyitems(config, items) -> None:
    """未启动后端时跳过 E2E，避免 ``pytest tests/`` 误报失败。"""
    if os.environ.get("RUN_E2E", "").strip() == "1":
        return
    if _e2e_backend_reachable():
        return
    skip = pytest.mark.skip(
        reason=(
            f"E2E 需要可访问的后端 ({E2E_API_BASE_URL}/health)。"
            "请运行仓库根目录 scripts/run-e2e.ps1，或启动 uvicorn 后设置 RUN_E2E=1。"
        )
    )
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


def _e2e_credentials() -> tuple[str, str] | None:
    email = os.environ.get("E2E_USER_EMAIL", "").strip()
    password = os.environ.get("E2E_USER_PASSWORD", "")
    if email and password:
        return email, password
    return None


@pytest.fixture
def e2e_auth_headers() -> dict[str, str]:
    """已登录用户的 Authorization 头（Chat/SimpleMem E2E 需 Gateway 注册用户归因）。"""
    creds = _e2e_credentials()
    if creds is None:
        pytest.skip(
            "设置 E2E_USER_EMAIL 与 E2E_USER_PASSWORD 以运行 Chat/SimpleMem E2E"
            "（匿名会话无法完成 Gateway 桥接归因）"
        )
    email, password = creds
    with httpx.Client(base_url=E2E_API_BASE_URL, timeout=30.0) as client:
        response = client.post(
            e2e_api_v1_path("auth", "token"),
            json={"email": email, "password": password},
        )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def http_client(e2e_auth_headers: dict[str, str]) -> Generator[httpx.Client, None, None]:
    """带认证的同步 HTTP 客户端。"""
    with httpx.Client(
        base_url=E2E_API_BASE_URL,
        timeout=60.0,
        headers=e2e_auth_headers,
    ) as client:
        yield client


@pytest.fixture
async def async_http_client(
    e2e_auth_headers: dict[str, str],
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """带认证的异步 HTTP 客户端。"""
    async with httpx.AsyncClient(
        base_url=E2E_API_BASE_URL,
        timeout=180.0,
        headers=e2e_auth_headers,
    ) as client:
        yield client
