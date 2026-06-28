"""火山 Seedream 生图 HTTP 客户端（直连 ``/images/generations``）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from domains.gateway.infrastructure.upstream.httpx_client_singleton import (
    get_upstream_httpx_client,
    track_upstream_request,
)

if TYPE_CHECKING:
    from domains.gateway.domain.provider.volcengine_image import VolcengineImageRequest


_PROVIDER = "volcengine"


def _request_timeout(total: float) -> httpx.Timeout:
    """构造分段超时：保留默认 connect/write/pool，只调整 read 总时间。"""
    return httpx.Timeout(connect=10.0, read=total, write=30.0, pool=5.0)


async def perform_volcengine_image_generation(
    request: VolcengineImageRequest,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """发送生图请求并解析 JSON 响应；非 2xx 抛 ``httpx.HTTPStatusError``。"""
    client = await get_upstream_httpx_client(_PROVIDER)
    async with track_upstream_request():
        resp = await client.post(
            request.url,
            headers={
                "Authorization": request.auth_header,
                "Content-Type": "application/json",
            },
            json=request.json_body,
            timeout=_request_timeout(timeout),
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            await resp.aread()
            raise
        data = resp.json()
    return data if isinstance(data, dict) else {"data": data}


async def perform_volcengine_image_probe(
    request: VolcengineImageRequest,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """探活别名。"""
    return await perform_volcengine_image_generation(request, timeout=timeout)


__all__ = ["perform_volcengine_image_generation", "perform_volcengine_image_probe"]
