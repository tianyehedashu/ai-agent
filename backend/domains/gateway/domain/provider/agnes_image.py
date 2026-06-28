"""Agnes（Sapiens）伪兼容生图请求构建（纯函数，无 HTTP/IO）。

Agnes 把 OpenAI **客户端 SDK** 的 ``extra_body`` 约定当成了线上协议字段：图生图 /
多图合成的输入图 ``image`` 与 ``response_format`` 必须置于**字面量嵌套**的
``extra_body`` 对象里（线上 JSON 真有这个 key），而非 OpenAI 官方那样摊平到顶层。
LiteLLM 的 ``aimage_generation`` 只会发标准 OpenAI Images 形状（顶层 ``response_format``、
无 ``image`` 数组、无字面量 ``extra_body``），表达不了该形状，故须绕过 LiteLLM 直连。

HTTP 执行在 ``infrastructure/upstream/agnes_image_client``；端点统一为
``{api_base}/images/generations``（文生图与图生图同址，无 ``/images/edits``）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from domains.gateway.domain.upstream.upstream_endpoint import resolve_upstream_endpoint
from domains.gateway.domain.upstream.upstream_profile import UpstreamProtocol

if TYPE_CHECKING:
    from collections.abc import Sequence

AGNES_PROVIDER = "agnes"
DEFAULT_AGNES_API_BASE = "https://apihub.agnes-ai.com/v1"
AGNES_DEFAULT_IMAGE_SIZE = "1024x1024"
# 与 gateway 既有生图路径（火山直连）一致默认返回内联 base64，便于响应自包含。
AGNES_DEFAULT_RESPONSE_FORMAT = "b64_json"
AGNES_IMG2IMG_TAG = "img2img"


@dataclass(frozen=True, slots=True)
class AgnesImageRequest:
    """Agnes 生图 HTTP 请求快照（探活与代理共用）。"""

    url: str
    auth_header: str
    json_body: dict[str, Any]


def should_use_agnes_direct_image(provider: str) -> bool:
    """是否应绕过 LiteLLM Router / ``aimage_generation`` 直连 Agnes。"""
    return provider.strip().lower() == AGNES_PROVIDER


def _coerce_image_inputs(value: Any) -> list[str]:
    """把单个 URL / URL 列表归一化为去空的字符串列表。"""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    return [s.strip() for s in items if isinstance(s, str) and s.strip()]


def extract_agnes_image_inputs(kwargs: dict[str, Any]) -> list[str]:
    """从入站 kwargs 抽取图生图输入图（兼容顶层 ``image`` 与嵌套 ``extra_body.image``）。

    调用方用 OpenAI SDK 的 ``extra_body={"image": [...]}`` 时，线上会摊平为顶层
    ``image``；若调用方直接照搬 Agnes 文档传字面量 ``extra_body``，则在嵌套层。
    """
    inputs = _coerce_image_inputs(kwargs.get("image"))
    if inputs:
        return inputs
    extra = kwargs.get("extra_body")
    if isinstance(extra, dict):
        return _coerce_image_inputs(extra.get("image"))
    return []


def extract_agnes_image_tags(kwargs: dict[str, Any]) -> list[str] | None:
    """从入站 kwargs 抽取并归一化 ``tags``（去空白/去空项；空则 None）。"""
    raw = kwargs.get("tags")
    if isinstance(raw, (list, tuple)):
        tags = [str(t).strip() for t in raw if str(t).strip()]
        return tags or None
    return None


def _coerce_n(value: Any) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def build_agnes_image_request(
    *,
    api_key: str,
    api_base: str | None,
    model: str,
    prompt: str,
    profile_id: str | None = None,
    size: str | None = None,
    n: int | str | None = None,
    seed: int | None = None,
    images: Sequence[str] = (),
    tags: Sequence[str] | None = None,
    response_format: str | None = None,
) -> AgnesImageRequest:
    """构建 Agnes ``/images/generations`` 请求快照（文生图 / 图生图通用）。

    ``images`` 非空即图生图：自动补 ``tags=["img2img"]``（调用方已显式给 tags 则尊重），
    并把 ``image`` 与 ``response_format`` 放进字面量 ``extra_body``。
    """
    if not prompt.strip():
        raise ValueError("prompt is required for image generation")
    resolved = resolve_upstream_endpoint(
        provider=AGNES_PROVIDER,
        profile_id=profile_id,
        api_base=api_base,
        protocol=UpstreamProtocol.OPENAI_COMPAT,
    )
    base = (resolved or DEFAULT_AGNES_API_BASE).rstrip("/")

    image_inputs = [s for s in images if isinstance(s, str) and s.strip()]
    extra_body: dict[str, Any] = {
        "response_format": (response_format or AGNES_DEFAULT_RESPONSE_FORMAT).strip()
        or AGNES_DEFAULT_RESPONSE_FORMAT
    }
    if image_inputs:
        extra_body["image"] = image_inputs

    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt.strip(),
        "size": (size or AGNES_DEFAULT_IMAGE_SIZE).strip() or AGNES_DEFAULT_IMAGE_SIZE,
        "extra_body": extra_body,
    }
    n_val = _coerce_n(n)
    if n_val is not None:
        body["n"] = n_val
    if seed is not None:
        body["seed"] = seed

    resolved_tags = list(tags) if tags else ([AGNES_IMG2IMG_TAG] if image_inputs else None)
    if resolved_tags:
        body["tags"] = resolved_tags

    return AgnesImageRequest(
        url=f"{base}/images/generations",
        auth_header=f"Bearer {api_key}",
        json_body=body,
    )


def build_agnes_image_probe_request(
    *,
    api_key: str,
    api_base: str | None,
    model: str,
    profile_id: str | None = None,
    size: str = AGNES_DEFAULT_IMAGE_SIZE,
    prompt: str = "ping",
) -> AgnesImageRequest:
    """探活：最小文生图请求。"""
    return build_agnes_image_request(
        api_key=api_key,
        api_base=api_base,
        model=model,
        prompt=prompt,
        profile_id=profile_id,
        size=size,
    )


__all__ = [
    "AGNES_DEFAULT_IMAGE_SIZE",
    "AGNES_DEFAULT_RESPONSE_FORMAT",
    "AGNES_PROVIDER",
    "DEFAULT_AGNES_API_BASE",
    "AgnesImageRequest",
    "build_agnes_image_probe_request",
    "build_agnes_image_request",
    "extract_agnes_image_inputs",
    "extract_agnes_image_tags",
    "should_use_agnes_direct_image",
]
