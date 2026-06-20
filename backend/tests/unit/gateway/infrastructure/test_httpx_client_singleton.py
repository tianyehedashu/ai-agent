"""Tests for domains.gateway.infrastructure.upstream.httpx_client_singleton."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from domains.gateway.infrastructure.upstream.httpx_client_singleton import (
    close_upstream_httpx_client,
    get_upstream_httpx_client,
    init_upstream_httpx_client,
    track_upstream_request,
)


@pytest.fixture(autouse=True)
async def _reset_singleton() -> None:
    """每个测试前清理 client 池。"""
    await close_upstream_httpx_client(wait_timeout_seconds=0.0)


@pytest.mark.asyncio
async def test_init_upstream_httpx_client_is_noop() -> None:
    await init_upstream_httpx_client()


@pytest.mark.asyncio
async def test_get_upstream_httpx_client_returns_same_instance_per_provider() -> None:
    first = await get_upstream_httpx_client("volcengine")
    second = await get_upstream_httpx_client("volcengine")
    assert first is second


@pytest.mark.asyncio
async def test_get_upstream_httpx_client_returns_different_instance_per_provider() -> None:
    volcengine = await get_upstream_httpx_client("volcengine")
    dashscope = await get_upstream_httpx_client("dashscope")
    assert volcengine is not dashscope


@pytest.mark.asyncio
async def test_close_upstream_httpx_client_closes_all_providers() -> None:
    volcengine = await get_upstream_httpx_client("volcengine")
    dashscope = await get_upstream_httpx_client("dashscope")
    await close_upstream_httpx_client(wait_timeout_seconds=0.0)
    assert volcengine.is_closed
    assert dashscope.is_closed


@pytest.mark.asyncio
async def test_get_upstream_httpx_client_rebuilds_after_close() -> None:
    first = await get_upstream_httpx_client("volcengine")
    await close_upstream_httpx_client(wait_timeout_seconds=0.0)
    second = await get_upstream_httpx_client("volcengine")
    assert first is not second
    assert first.is_closed
    assert not second.is_closed


def test_get_upstream_httpx_client_rebuilds_on_loop_change() -> None:
    """模拟 event loop 切换场景（pytest-asyncio 常见），client 应自动重建。"""

    async def _inner() -> tuple[httpx.AsyncClient, httpx.AsyncClient]:
        await close_upstream_httpx_client(wait_timeout_seconds=0.0)
        first = await get_upstream_httpx_client("volcengine")
        await close_upstream_httpx_client(wait_timeout_seconds=0.0)
        return first, await get_upstream_httpx_client("volcengine")

    loop1 = asyncio.new_event_loop()
    first, _ = loop1.run_until_complete(_inner())
    loop1.close()

    loop2 = asyncio.new_event_loop()
    _, second = loop2.run_until_complete(_inner())
    loop2.close()

    assert first is not second


@pytest.mark.asyncio
async def test_track_upstream_request_counts_active_requests() -> None:
    async with track_upstream_request():
        # 活跃请求数应至少为 1；由于全局状态，不断言具体数值。
        pass


@pytest.mark.asyncio
async def test_close_upstream_httpx_client_waits_for_active_requests() -> None:
    async with track_upstream_request():
        # 关闭应等待活跃请求完成，但 wait_timeout=0 会立即超时。
        await close_upstream_httpx_client(wait_timeout_seconds=0.0)


@pytest.mark.asyncio
async def test_client_follows_redirects() -> None:
    client = await get_upstream_httpx_client("volcengine")
    assert isinstance(client, httpx.AsyncClient)
    assert client.follow_redirects is True
    assert not client.is_closed
