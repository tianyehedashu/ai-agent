"""HTTP 路径拼接 — 单一来源（ROOT_PATH + API_PREFIX）。"""

from __future__ import annotations

from bootstrap.config import get_settings


def _normalize_segments(*parts: str) -> list[str]:
    segments: list[str] = []
    for part in parts:
        if not part:
            continue
        for piece in part.strip("/").split("/"):
            if piece:
                segments.append(piece)
    return segments


def service_path(*segments: str) -> str:
    """``ROOT_PATH`` + segments（如 ``/ai-agent/health``）。"""
    root_parts = _normalize_segments(get_settings().root_path)
    rest = _normalize_segments(*segments)
    combined = root_parts + rest
    if not combined:
        return "/"
    return "/" + "/".join(combined)


def api_v1_path(*segments: str) -> str:
    """``{ROOT_PATH}{API_PREFIX}/{segments}``（如 ``/ai-agent/api/v1/gateway``）。"""
    settings = get_settings()
    base_parts = _normalize_segments(settings.root_path, settings.api_prefix)
    rest = _normalize_segments(*segments)
    combined = base_parts + rest
    return "/" + "/".join(combined)


def openai_compat_base() -> str:
    """OpenAI SDK ``base_url``（含 ``/v1`` 尾段）。"""
    return api_v1_path("openai", "v1")


def anthropic_compat_base() -> str:
    """Anthropic SDK ``base_url``（无 ``/v1`` 尾段）。"""
    return api_v1_path("anthropic")


def listing_studio_images_serve_prefix() -> str:
    """Listing Studio 本地图片对外 URL 前缀。"""
    return api_v1_path("listing-studio", "images")


def public_api_url(origin: str, *segments: str) -> str:
    """请求 origin + API 路径（外链、MCP client-config 等）。"""
    return f"{origin.rstrip('/')}{api_v1_path(*segments)}"


# 迁移前 DB/配置中的默认本地图片前缀（ROOT_PATH 启用时需动态覆盖）
LEGACY_LISTING_STUDIO_IMAGES_PREFIX = "/api/v1/listing-studio/images"


def effective_listing_studio_serve_prefix(stored: str | None) -> str:
    """DB 未配置或仍为旧默认值时，使用当前 ROOT_PATH 下的前缀。"""
    if (
        stored is None
        or not stored.strip()
        or stored.strip() == LEGACY_LISTING_STUDIO_IMAGES_PREFIX
    ):
        return listing_studio_images_serve_prefix()
    return stored.strip()
