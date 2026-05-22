"""视频生成探活响应预览提取。"""

from __future__ import annotations

from contextlib import suppress
from typing import Any


def video_generation_probe_preview(video_response: Any) -> str:
    preview = ""
    with suppress(Exception):
        status: str | None
        video_id: str | None
        if isinstance(video_response, dict):
            status = video_response.get("status") if isinstance(video_response.get("status"), str) else None
            video_id = video_response.get("id") if isinstance(video_response.get("id"), str) else None
        else:
            raw_status = getattr(video_response, "status", None)
            raw_id = getattr(video_response, "id", None)
            status = raw_status if isinstance(raw_status, str) else None
            video_id = raw_id if isinstance(raw_id, str) else None
        if status and video_id:
            preview = f"{status}: {video_id}"
        elif video_id:
            preview = video_id
        elif status:
            preview = status
    return preview[:100]


__all__ = ["video_generation_probe_preview"]
