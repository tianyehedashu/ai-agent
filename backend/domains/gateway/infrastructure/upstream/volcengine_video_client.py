"""火山 Seedance 视频生成的 HTTP 客户端（直连 ``/contents/generations/tasks``）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from domains.gateway.infrastructure.upstream.httpx_client_singleton import (
    get_upstream_httpx_client,
    track_upstream_request,
)

if TYPE_CHECKING:
    from domains.gateway.domain.policies.volcengine_video import VolcengineVideoCreateRequest


_PROVIDER = "volcengine"


def _request_timeout(total: float) -> httpx.Timeout:
    return httpx.Timeout(connect=10.0, read=total, write=30.0, pool=5.0)


async def perform_volcengine_video_create(
    request: VolcengineVideoCreateRequest,
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """创建视频生成任务并解析 JSON 响应；非 2xx 抛 ``httpx.HTTPStatusError``。"""
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
    if not isinstance(data, dict):
        raise ValueError("volcengine video create returned non-object JSON")
    return data


__all__ = ["perform_volcengine_video_create"]
