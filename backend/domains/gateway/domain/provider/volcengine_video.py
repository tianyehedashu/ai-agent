"""火山引擎 Seedance 视频生成直连策略（纯函数，无 HTTP/IO）。

LiteLLM ``avideo_generation`` 当前不支持 ``volcengine`` provider，
必须直连 ``{api_base}/contents/generations/tasks`` 并把 ``real_model`` 作为 ``model``。
HTTP 执行在 ``infrastructure/upstream``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .provider_api_base import (
    get_default_api_base,
    resolve_effective_api_base,
)
from .volcengine_direct import should_use_volcengine_direct_upstream

DEFAULT_VOLCENGINE_API_BASE = (
    get_default_api_base("volcengine") or "https://ark.cn-beijing.volces.com/api/v3"
)


VOLCENGINE_VIDEO_POLL_INTERVAL_SECONDS = 5.0
VOLCENGINE_VIDEO_POLL_MAX_ATTEMPTS = 120  # 5s * 120 ≈ 10min

_VOLCENGINE_VIDEO_TERMINAL_STATUSES = frozenset(
    {"succeeded", "completed", "failed", "expired", "cancelled"}
)
_VOLCENGINE_VIDEO_IN_PROGRESS_STATUSES = frozenset({"queued", "running", "processing"})


@dataclass(frozen=True, slots=True)
class VolcengineVideoGetRequest:
    """火山视频生成任务查询的 HTTP 请求快照。"""

    url: str
    auth_header: str


def build_volcengine_video_get_request(
    *,
    api_key: str,
    api_base: str | None,
    task_id: str,
) -> VolcengineVideoGetRequest:
    """构建 Seedance 视频任务查询请求。"""
    base = (
        resolve_effective_api_base("volcengine", api_base) or DEFAULT_VOLCENGINE_API_BASE
    ).rstrip("/")
    cleaned_id = task_id.strip()
    if not cleaned_id:
        raise ValueError("volcengine video task id is required")
    return VolcengineVideoGetRequest(
        url=f"{base}/contents/generations/tasks/{cleaned_id}",
        auth_header=f"Bearer {api_key}",
    )


def is_volcengine_video_terminal_status(status: str | None) -> bool:
    if not isinstance(status, str) or not status.strip():
        return False
    return status.strip().lower() in _VOLCENGINE_VIDEO_TERMINAL_STATUSES


def is_volcengine_video_in_progress_status(status: str | None) -> bool:
    if not isinstance(status, str) or not status.strip():
        return False
    normalized = status.strip().lower()
    return normalized in _VOLCENGINE_VIDEO_IN_PROGRESS_STATUSES


def extract_volcengine_video_url(data: dict[str, Any]) -> str | None:
    """从方舟任务响应提取 ``content.video_url``（或兼容字段）。"""
    content = data.get("content")
    if isinstance(content, dict):
        raw = content.get("video_url")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    raw_top = data.get("video_url")
    if isinstance(raw_top, str) and raw_top.strip():
        return raw_top.strip()
    result_url = data.get("result_url")
    if isinstance(result_url, str) and result_url.strip():
        return result_url.strip()
    return None


@dataclass(frozen=True, slots=True)
class VolcengineVideoCreateRequest:
    """火山视频生成任务创建的 HTTP 请求快照。"""

    url: str
    auth_header: str
    json_body: dict[str, Any]


def should_use_volcengine_direct_video(provider: str) -> bool:
    """是否应绕过 LiteLLM Router / ``avideo_generation``，改走方舟任务 API。"""
    return should_use_volcengine_direct_upstream(provider)


def normalize_volcengine_video_model(model_id: str) -> str:
    """将 ``real_model`` / ``volcengine/...`` 规范为上游 ``model`` 字段。"""
    cleaned = (model_id or "").strip()
    if not cleaned:
        return cleaned
    lower = cleaned.lower()
    if lower.startswith("volcengine/"):
        return cleaned.split("/", 1)[1]
    return cleaned


def parse_video_duration_seconds(seconds: str | int | None, *, default: int = 5) -> int:
    if seconds is None:
        return default
    try:
        val = int(str(seconds).strip())
    except ValueError:
        return default
    return val if val > 0 else default


def build_volcengine_video_create_request(
    *,
    api_key: str,
    api_base: str | None,
    model_id: str,
    prompt: str,
    seconds: str | int | None = None,
    watermark: bool = False,
) -> VolcengineVideoCreateRequest:
    """根据凭据与 prompt 构建 Seedance 视频任务创建请求。"""
    base = (
        resolve_effective_api_base("volcengine", api_base) or DEFAULT_VOLCENGINE_API_BASE
    ).rstrip("/")
    upstream_model = normalize_volcengine_video_model(model_id)
    duration = parse_video_duration_seconds(seconds)
    return VolcengineVideoCreateRequest(
        url=f"{base}/contents/generations/tasks",
        auth_header=f"Bearer {api_key}",
        json_body={
            "model": upstream_model,
            "content": [{"type": "text", "text": prompt}],
            "duration": duration,
            "watermark": watermark,
        },
    )


def map_volcengine_video_task_to_openai(
    data: dict[str, Any],
    *,
    fallback_model: str,
) -> dict[str, Any]:
    """将方舟任务创建/查询响应映射为 OpenAI 兼容 ``/v1/videos`` 结构。"""
    task_id = data.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("volcengine video task response missing id")
    status = data.get("status")
    model = data.get("model") if isinstance(data.get("model"), str) else fallback_model
    mapped: dict[str, Any] = {
        "id": task_id,
        "object": "video",
        "status": status if isinstance(status, str) else "queued",
        "model": normalize_volcengine_video_model(model),
    }
    video_url = extract_volcengine_video_url(data)
    if video_url:
        mapped["video"] = {"url": video_url}
        mapped["url"] = video_url
    return mapped


__all__ = [
    "DEFAULT_VOLCENGINE_API_BASE",
    "VOLCENGINE_VIDEO_POLL_INTERVAL_SECONDS",
    "VOLCENGINE_VIDEO_POLL_MAX_ATTEMPTS",
    "VolcengineVideoCreateRequest",
    "VolcengineVideoGetRequest",
    "build_volcengine_video_create_request",
    "build_volcengine_video_get_request",
    "extract_volcengine_video_url",
    "is_volcengine_video_in_progress_status",
    "is_volcengine_video_terminal_status",
    "map_volcengine_video_task_to_openai",
    "normalize_volcengine_video_model",
    "parse_video_duration_seconds",
    "should_use_volcengine_direct_video",
]
