"""火山引擎 Seedream 探活请求构建（纯函数，无 HTTP/IO）。

LiteLLM ``aimage_generation`` 当前不支持火山 ``ep-xxx`` image endpoint，
必须直连 ``{api_base}/images/generations`` 并把 image endpoint_id 作为 ``model``。
本模块只产出请求"快照"，HTTP 执行在 ``infrastructure/external``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_VOLCENGINE_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"


@dataclass(frozen=True, slots=True)
class VolcengineImageProbeRequest:
    """火山生图探活的 HTTP 请求快照。"""

    url: str
    auth_header: str
    json_body: dict[str, Any]


def build_volcengine_image_probe_request(
    *,
    api_key: str,
    api_base: str | None,
    image_endpoint_id: str,
    size: str = "1024x1024",
) -> VolcengineImageProbeRequest:
    """根据凭据 + image endpoint 构建探活请求；``size`` 与 Agent 探活默认对齐。"""
    base = (api_base or DEFAULT_VOLCENGINE_API_BASE).rstrip("/")
    return VolcengineImageProbeRequest(
        url=f"{base}/images/generations",
        auth_header=f"Bearer {api_key}",
        json_body={
            "model": image_endpoint_id,
            "prompt": "ping",
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        },
    )


__all__ = [
    "DEFAULT_VOLCENGINE_API_BASE",
    "VolcengineImageProbeRequest",
    "build_volcengine_image_probe_request",
]
