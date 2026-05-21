"""火山 Seedream 探活的 HTTP 客户端（直连 ``/images/generations``）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from domains.gateway.domain.policies.volcengine_image_probe import (
        VolcengineImageProbeRequest,
    )


async def perform_volcengine_image_probe(
    request: VolcengineImageProbeRequest,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """发送探活请求并解析 JSON 响应；非 2xx 抛 ``httpx.HTTPStatusError``。"""
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
    return data if isinstance(data, dict) else {"data": data}


__all__ = ["perform_volcengine_image_probe"]
