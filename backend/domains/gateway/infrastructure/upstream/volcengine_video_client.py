"""火山 Seedance 视频生成的 HTTP 客户端（直连 ``/contents/generations/tasks``）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from domains.gateway.domain.policies.volcengine_video import VolcengineVideoCreateRequest


async def perform_volcengine_video_create(
    request: VolcengineVideoCreateRequest,
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """创建视频生成任务并解析 JSON 响应；非 2xx 抛 ``httpx.HTTPStatusError``。"""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            request.url,
            headers={
                "Authorization": request.auth_header,
                "Content-Type": "application/json",
            },
            json=request.json_body,
        )
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("volcengine video create returned non-object JSON")
    return data


__all__ = ["perform_volcengine_video_create"]
