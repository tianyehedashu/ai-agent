"""DashScope OpenAI 兼容 Embedding 的 HTTP 客户端。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from domains.gateway.domain.policies.dashscope_embedding import DashscopeEmbeddingRequest


async def perform_dashscope_embedding(
    request: DashscopeEmbeddingRequest,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """发送 Embedding 请求并返回 OpenAI 形 JSON；非 2xx 抛 ``httpx.HTTPStatusError``。"""
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
    if isinstance(data, dict):
        return data
    return {"data": data}


__all__ = ["perform_dashscope_embedding"]
