"""火山引擎 Seedance 视频生成直连策略（纯函数，无 HTTP/IO）。

LiteLLM ``avideo_generation`` 当前不支持 ``volcengine`` provider，
必须直连 ``{api_base}/contents/generations/tasks`` 并把 ``real_model`` 作为 ``model``。
HTTP 执行在 ``infrastructure/upstream``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.gateway.domain.provider_api_base import (
    get_default_api_base,
    resolve_effective_api_base,
)

DEFAULT_VOLCENGINE_API_BASE = (
    get_default_api_base("volcengine") or "https://ark.cn-beijing.volces.com/api/v3"
)


@dataclass(frozen=True, slots=True)
class VolcengineVideoCreateRequest:
    """火山视频生成任务创建的 HTTP 请求快照。"""

    url: str
    auth_header: str
    json_body: dict[str, Any]


def should_use_volcengine_direct_video(provider: str) -> bool:
    """是否应绕过 LiteLLM Router / ``avideo_generation``，改走方舟任务 API。"""
    return (provider or "").strip().lower() == "volcengine"


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
    base = (resolve_effective_api_base("volcengine", api_base) or DEFAULT_VOLCENGINE_API_BASE).rstrip(
        "/"
    )
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
    """将方舟任务创建响应映射为 OpenAI 兼容 ``/v1/videos`` 结构。"""
    task_id = data.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("volcengine video task response missing id")
    status = data.get("status")
    model = data.get("model") if isinstance(data.get("model"), str) else fallback_model
    return {
        "id": task_id,
        "object": "video",
        "status": status if isinstance(status, str) else "queued",
        "model": normalize_volcengine_video_model(model),
    }


__all__ = [
    "DEFAULT_VOLCENGINE_API_BASE",
    "VolcengineVideoCreateRequest",
    "build_volcengine_video_create_request",
    "map_volcengine_video_task_to_openai",
    "normalize_volcengine_video_model",
    "parse_video_duration_seconds",
    "should_use_volcengine_direct_video",
]
