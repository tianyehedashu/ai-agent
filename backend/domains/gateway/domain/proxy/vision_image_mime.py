"""视觉内联 data URL 的 MIME 映射（与常见图片扩展名对齐，不依赖 Agent 域）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

VISION_INLINE_MIME_BY_EXTENSION: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def guess_vision_inline_mime(path: Path) -> str:
    return VISION_INLINE_MIME_BY_EXTENSION.get(path.suffix.lower(), "image/jpeg")


__all__ = ["VISION_INLINE_MIME_BY_EXTENSION", "guess_vision_inline_mime"]
