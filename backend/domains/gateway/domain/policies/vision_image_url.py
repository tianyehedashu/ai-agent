"""视觉多模态 image_url 解析策略（纯函数）。"""

from __future__ import annotations

from urllib.parse import urlparse

LISTING_STUDIO_IMAGES_PATH_MARKER = "/listing-studio/images/"


def parse_listing_studio_image_filename(url: str) -> str | None:
    """从相对或绝对 URL 中解析 listing-studio 本地图片文件名。"""
    raw = url.strip()
    if not raw or raw.startswith("data:"):
        return None

    path = urlparse(raw).path if "://" in raw else raw.split("?", 1)[0]
    idx = path.find(LISTING_STUDIO_IMAGES_PATH_MARKER)
    if idx < 0:
        return None

    rest = path[idx + len(LISTING_STUDIO_IMAGES_PATH_MARKER) :].strip("/")
    if not rest or "/" in rest or ".." in rest:
        return None
    return rest


def should_inline_vision_image_url(url: str) -> bool:
    """上游（如火山）不接受相对路径时，是否应尝试从本地存储内联为 data URL。"""
    u = url.strip()
    if not u or u.startswith("data:"):
        return False
    if u.startswith("/"):
        return True
    return parse_listing_studio_image_filename(u) is not None


__all__ = [
    "LISTING_STUDIO_IMAGES_PATH_MARKER",
    "parse_listing_studio_image_filename",
    "should_inline_vision_image_url",
]
