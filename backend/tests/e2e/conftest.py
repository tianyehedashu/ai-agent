"""E2E 共享 fixture（真实 HTTP，依赖 localhost:8000 与可选登录凭据）。"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import os

import httpx
import pytest

from tests.e2e.config import E2E_API_BASE_URL


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
            "/api/v1/auth/token",
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
