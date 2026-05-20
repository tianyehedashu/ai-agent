"""Listing Studio 图片上传校验策略（纯函数）。"""

from __future__ import annotations

from libs.exceptions import ValidationError

ALLOWED_IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def validate_image_upload(
    content_type: str | None,
    size_bytes: int,
    max_bytes: int,
) -> str:
    """校验上传图片 MIME 与大小，返回文件扩展名。

    Raises:
        ValidationError: MIME 不支持或超出大小限制
    """
    if not content_type or content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError(
            "仅支持 JPEG、PNG、WebP、GIF 图片",
            details={"field": "content_type"},
        )
    if size_bytes <= 0:
        raise ValidationError("上传文件为空", details={"field": "file"})
    if size_bytes > max_bytes:
        max_mb = max(1, max_bytes // (1024 * 1024))
        raise ValidationError(
            f"图片大小不能超过 {max_mb} MB",
            details={"field": "file"},
        )
    return ALLOWED_IMAGE_CONTENT_TYPES[content_type]


__all__ = ["ALLOWED_IMAGE_CONTENT_TYPES", "validate_image_upload"]
