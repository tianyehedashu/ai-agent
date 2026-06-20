"""DashScope OpenAI 兼容 Embedding 的 HTTP 客户端。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from domains.gateway.infrastructure.upstream.httpx_client_singleton import (
    get_upstream_httpx_client,
    track_upstream_request,
)

if TYPE_CHECKING:
    from domains.gateway.domain.policies.dashscope_embedding import DashscopeEmbeddingRequest


_PROVIDER = "dashscope"


def _request_timeout(total: float) -> httpx.Timeout:
    return httpx.Timeout(connect=10.0, read=total, write=30.0, pool=5.0)


async def perform_dashscope_embedding(
    request: DashscopeEmbeddingRequest,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """发送 Embedding 请求并返回 OpenAI 形 JSON；非 2xx 抛 ``httpx.HTTPStatusError``。"""
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
    if isinstance(data, dict):
        return data
    return {"data": data}


__all__ = ["perform_dashscope_embedding"]
