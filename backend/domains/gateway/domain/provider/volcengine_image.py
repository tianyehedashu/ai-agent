"""火山引擎 Seedream 生图请求构建（纯函数，无 HTTP/IO）。

LiteLLM ``aimage_generation`` 当前不支持火山 ``ep-xxx`` image endpoint，
必须直连 ``{api_base}/images/generations`` 并把 image endpoint_id 作为 ``model``。
HTTP 执行在 ``infrastructure/upstream/volcengine_image_client``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.gateway.domain.upstream.upstream_endpoint import resolve_upstream_endpoint
from domains.gateway.domain.upstream.upstream_profile import UpstreamProtocol

from .provider_api_base import get_default_api_base
from .volcengine_direct import should_use_volcengine_direct_upstream

DEFAULT_VOLCENGINE_API_BASE = (
    get_default_api_base("volcengine") or "https://ark.cn-beijing.volces.com/api/v3"
)

VOLCENGINE_IMAGE_ENDPOINT_EXTRA_KEY = "image_endpoint_id"

# Seedream / 方舟生图：总像素数下限（1920×1920）
VOLCENGINE_MIN_IMAGE_PIXELS = 3_686_400
VOLCENGINE_DEFAULT_IMAGE_SIZE = "1920x1920"


@dataclass(frozen=True, slots=True)
class VolcengineImageRequest:
    """火山生图 HTTP 请求快照（探活与代理共用）。"""

    url: str
    auth_header: str
    json_body: dict[str, Any]


# 兼容旧名
VolcengineImageProbeRequest = VolcengineImageRequest


def should_use_volcengine_direct_image(provider: str) -> bool:
    """是否应绕过 LiteLLM Router / ``aimage_generation``。"""
    return should_use_volcengine_direct_upstream(provider)


def parse_volcengine_image_endpoint_id(extra: dict[str, Any] | None) -> str | None:
    """从凭据 ``extra`` 读取火山图像接入点（``ep-xxx``）。"""
    raw = (extra or {}).get(VOLCENGINE_IMAGE_ENDPOINT_EXTRA_KEY)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


VOLCENGINE_IMAGE_CREDENTIAL_SETUP_MESSAGE = (
    "火山生图模型须先在绑定凭据的 extra 中配置 image_endpoint_id（ep-m-xxx，与 API Key 同账号）；"
    "可在 Gateway 凭据页编辑「生图接入点 ID」"
)


def assert_volcengine_image_credential_ready(
    *,
    provider: str,
    capability: str,
    extra: dict[str, Any] | None,
) -> None:
    """主调用面为 image 且 provider 为 volcengine 时，凭据 extra 须含 image_endpoint_id。"""
    from libs.exceptions import ValidationError

    if provider.strip().lower() != "volcengine":
        return
    if capability.strip().lower() != "image":
        return
    if parse_volcengine_image_endpoint_id(extra) is None:
        raise ValidationError(VOLCENGINE_IMAGE_CREDENTIAL_SETUP_MESSAGE)


def parse_image_dimensions(size: str) -> tuple[int, int] | None:
    """解析 ``WIDTHxHEIGHT``；非法格式返回 ``None``。"""
    parts = size.strip().lower().split("x")
    if len(parts) != 2:
        return None
    try:
        w, h = int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return w, h


def image_pixel_count(size: str) -> int | None:
    dims = parse_image_dimensions(size)
    if dims is None:
        return None
    return dims[0] * dims[1]


def resolve_volcengine_image_size(size: str | None) -> str:
    """校验或回落火山生图 ``size``（不满足最小像素时 ``ValueError``）。"""
    raw = (size or VOLCENGINE_DEFAULT_IMAGE_SIZE).strip()
    pixels = image_pixel_count(raw)
    if pixels is None:
        raise ValueError(
            f"invalid image size {raw!r}: expected WIDTHxHEIGHT (e.g. {VOLCENGINE_DEFAULT_IMAGE_SIZE})"
        )
    if pixels < VOLCENGINE_MIN_IMAGE_PIXELS:
        raise ValueError(
            f"image size {raw} is {pixels} pixels; Volcengine requires at least "
            f"{VOLCENGINE_MIN_IMAGE_PIXELS} pixels (e.g. {VOLCENGINE_DEFAULT_IMAGE_SIZE})"
        )
    return raw


def _coerce_image_n(value: int | str | None) -> int:
    if value is None:
        return 1
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    return n if n > 0 else 1


def build_volcengine_image_request(
    *,
    api_key: str,
    api_base: str | None,
    image_endpoint_id: str,
    profile_id: str | None = None,
    size: str = VOLCENGINE_DEFAULT_IMAGE_SIZE,
    prompt: str = "ping",
    n: int | str | None = 1,
    response_format: str = "b64_json",
) -> VolcengineImageRequest:
    """根据凭据 + image endpoint 构建生图 HTTP 请求。"""
    resolved = resolve_upstream_endpoint(
        provider="volcengine",
        profile_id=profile_id,
        api_base=api_base,
        protocol=UpstreamProtocol.OPENAI_COMPAT,
    )
    base = (resolved or DEFAULT_VOLCENGINE_API_BASE).rstrip("/")
    resolved_size = resolve_volcengine_image_size(size)
    body: dict[str, Any] = {
        "model": image_endpoint_id,
        "prompt": prompt,
        "size": resolved_size,
        "n": _coerce_image_n(n),
        "response_format": response_format,
    }
    return VolcengineImageRequest(
        url=f"{base}/images/generations",
        auth_header=f"Bearer {api_key}",
        json_body=body,
    )


def build_volcengine_image_probe_request(
    *,
    api_key: str,
    api_base: str | None,
    image_endpoint_id: str,
    profile_id: str | None = None,
    size: str = VOLCENGINE_DEFAULT_IMAGE_SIZE,
    prompt: str = "ping",
    n: int | str | None = 1,
    response_format: str = "b64_json",
) -> VolcengineImageRequest:
    """探活别名，与 ``build_volcengine_image_request`` 相同。"""
    return build_volcengine_image_request(
        api_key=api_key,
        api_base=api_base,
        image_endpoint_id=image_endpoint_id,
        profile_id=profile_id,
        size=size,
        prompt=prompt,
        n=n,
        response_format=response_format,
    )


def build_volcengine_image_generation_request(
    *,
    api_key: str,
    api_base: str | None,
    image_endpoint_id: str,
    profile_id: str | None = None,
    prompt: str,
    size: str | None = None,
    n: int | str | None = None,
    response_format: str | None = None,
) -> VolcengineImageRequest:
    """代理 ``/v1/images/generations`` 入参 → 方舟请求快照。"""
    if not prompt.strip():
        raise ValueError("prompt is required for image generation")
    return build_volcengine_image_request(
        api_key=api_key,
        api_base=api_base,
        image_endpoint_id=image_endpoint_id,
        profile_id=profile_id,
        size=resolve_volcengine_image_size(size),
        prompt=prompt.strip(),
        n=n,
        response_format=(response_format or "b64_json").strip() or "b64_json",
    )


__all__ = [
    "DEFAULT_VOLCENGINE_API_BASE",
    "VOLCENGINE_DEFAULT_IMAGE_SIZE",
    "VOLCENGINE_IMAGE_CREDENTIAL_SETUP_MESSAGE",
    "VOLCENGINE_IMAGE_ENDPOINT_EXTRA_KEY",
    "VOLCENGINE_MIN_IMAGE_PIXELS",
    "VolcengineImageProbeRequest",
    "VolcengineImageRequest",
    "assert_volcengine_image_credential_ready",
    "build_volcengine_image_generation_request",
    "build_volcengine_image_probe_request",
    "build_volcengine_image_request",
    "image_pixel_count",
    "parse_image_dimensions",
    "parse_volcengine_image_endpoint_id",
    "resolve_volcengine_image_size",
    "should_use_volcengine_direct_image",
]
