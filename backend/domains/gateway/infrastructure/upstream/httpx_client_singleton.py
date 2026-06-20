"""Gateway 上游直连 HTTP 客户端池。

按 provider 维护独立的 httpx.AsyncClient，避免不同上游互相争抢连接；
每个 provider 的连接池大小、keepalive 等行为可通过 settings 配置。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx

from bootstrap.config import settings
from utils.logging import get_logger

if TYPE_CHECKING:
    from types import TracebackType

logger = get_logger(__name__)

# 默认分段超时：connect/read/write/pool。
# pool=30s 避免高并发下等待连接池可用时触发 PoolTimeout。
_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=30.0)

# provider -> client / loop_id
_provider_clients: dict[str, httpx.AsyncClient] = {}
_provider_loop_ids: dict[str, int] = {}
_client_lock = asyncio.Lock()

_active_requests = 0
_shutdown_event = asyncio.Event()
_shutdown_event.set()


class _UpstreamRequestTracker:
    """上下文管理器：跟踪当前正在进行的上游请求数，供关闭时等待。"""

    async def __aenter__(self) -> _UpstreamRequestTracker:
        global _active_requests  # pylint: disable=global-statement
        _active_requests += 1
        _shutdown_event.clear()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        global _active_requests  # pylint: disable=global-statement
        _active_requests = max(0, _active_requests - 1)
        if _active_requests == 0:
            _shutdown_event.set()


def track_upstream_request() -> _UpstreamRequestTracker:
    """返回一个异步上下文管理器，进入/退出时增减活跃请求计数。"""
    return _UpstreamRequestTracker()


def _build_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=max(
            1, getattr(settings, "gateway_upstream_httpx_max_connections", 100)
        ),
        max_keepalive_connections=max(
            1,
            getattr(settings, "gateway_upstream_httpx_max_keepalive_connections", 20),
        ),
        keepalive_expiry=max(
            0.0, getattr(settings, "gateway_upstream_httpx_keepalive_expiry", 30.0)
        ),
    )


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=_DEFAULT_TIMEOUT,
        limits=_build_limits(),
        follow_redirects=True,
        verify=True,
        http2=False,
    )


async def init_upstream_httpx_client() -> None:
    """启动期初始化；由 bootstrap/main.py lifespan 调用。

    client 采用懒加载策略，此处仅记录日志，实际 client 在首次请求时创建。
    """
    logger.debug("Upstream httpx client pools ready (lazy load)")


async def close_upstream_httpx_client(
    *,
    wait_timeout_seconds: float = 30.0,
) -> None:
    """关闭期清理；先等待活跃请求完成（带超时），再关闭所有 provider client。"""
    if _active_requests > 0:
        logger.info(
            "Waiting for %d active upstream httpx requests to complete...",
            _active_requests,
        )
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=wait_timeout_seconds)
        except TimeoutError:
            logger.warning(
                "Timeout waiting for %d active upstream httpx requests; forcing close",
                _active_requests,
            )

    async with _client_lock:
        for provider, client in list(_provider_clients.items()):
            if not client.is_closed:
                await client.aclose()
                logger.debug("Upstream httpx client closed: provider=%s", provider)
        _provider_clients.clear()
        _provider_loop_ids.clear()


async def get_upstream_httpx_client(provider: str = "default") -> httpx.AsyncClient:
    """按 provider 获取独立连接池的 httpx.AsyncClient。

    同一 provider 在当前 event loop 内返回同一实例；检测到 loop 切换时
    会关闭旧 client 并重建，避免 pytest-asyncio 等场景下跨 loop 使用。
    使用 asyncio.Lock 保护创建/重建过程，避免竞态。
    """
    global _provider_clients, _provider_loop_ids  # pylint: disable=global-statement
    loop_id = id(asyncio.get_running_loop())
    async with _client_lock:
        existing = _provider_clients.get(provider)
        existing_loop_id = _provider_loop_ids.get(provider)
        if existing_loop_id is not None and existing_loop_id != loop_id:
            if existing is not None and not existing.is_closed:
                await existing.aclose()
            _provider_clients.pop(provider, None)
            _provider_loop_ids.pop(provider, None)
            existing = None
        if existing is None or existing.is_closed:
            existing = _build_client()
            _provider_clients[provider] = existing
            _provider_loop_ids[provider] = loop_id
            logger.debug(
                "Upstream httpx client created: provider=%s loop_id=%s",
                provider,
                loop_id,
            )
        return existing


__all__ = [
    "close_upstream_httpx_client",
    "get_upstream_httpx_client",
    "init_upstream_httpx_client",
    "track_upstream_request",
]
