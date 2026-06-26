"""火山 Seedance 视频生成的 HTTP 客户端（直连 ``/contents/generations/tasks``）。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx

from domains.gateway.domain.policies.volcengine_video import (
    VOLCENGINE_VIDEO_POLL_INTERVAL_SECONDS,
    VOLCENGINE_VIDEO_POLL_MAX_ATTEMPTS,
    is_volcengine_video_in_progress_status,
    is_volcengine_video_terminal_status,
)
from domains.gateway.infrastructure.upstream.httpx_client_singleton import (
    get_upstream_httpx_client,
    track_upstream_request,
)

if TYPE_CHECKING:
    from domains.gateway.domain.policies.volcengine_video import (
        VolcengineVideoCreateRequest,
        VolcengineVideoGetRequest,
    )

logger = logging.getLogger(__name__)

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


async def perform_volcengine_video_get(
    request: VolcengineVideoGetRequest,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """查询视频生成任务状态；非 2xx 抛 ``httpx.HTTPStatusError``。"""
    client = await get_upstream_httpx_client(_PROVIDER)
    async with track_upstream_request():
        resp = await client.get(
            request.url,
            headers={
                "Authorization": request.auth_header,
                "Content-Type": "application/json",
            },
            timeout=_request_timeout(timeout),
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            await resp.aread()
            raise
        data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("volcengine video get returned non-object JSON")
    return data


async def poll_volcengine_video_task(
    request: VolcengineVideoGetRequest,
    *,
    poll_interval: float = VOLCENGINE_VIDEO_POLL_INTERVAL_SECONDS,
    max_attempts: int = VOLCENGINE_VIDEO_POLL_MAX_ATTEMPTS,
    request_timeout: float = 60.0,
) -> dict[str, Any]:
    """轮询方舟视频任务直至终态或超时。"""
    last: dict[str, Any] | None = None
    for attempt in range(max_attempts):
        if attempt > 0:
            await asyncio.sleep(poll_interval)
        try:
            data = await perform_volcengine_video_get(request, timeout=request_timeout)
        except Exception as exc:
            logger.warning(
                "volcengine video poll attempt %d failed: %s",
                attempt + 1,
                exc,
            )
            continue
        last = data
        status = data.get("status")
        if is_volcengine_video_terminal_status(
            status if isinstance(status, str) else None
        ):
            return data
        if not is_volcengine_video_in_progress_status(
            status if isinstance(status, str) else None
        ):
            return data
        logger.debug(
            "volcengine video poll %d/%d: status=%s",
            attempt + 1,
            max_attempts,
            status,
        )
    if last is not None:
        return last
    raise TimeoutError("volcengine video task polling timed out without response")


__all__ = [
    "perform_volcengine_video_create",
    "perform_volcengine_video_get",
    "poll_volcengine_video_task",
]
