"""
Local Image Store - 本地图片存储

将 base64 编码的图片保存到本地目录，返回可访问的 URL 路径。
生产环境应替换为对象存储（S3、OSS）。
"""

import base64
from pathlib import Path
import uuid

from utils.logging import get_logger

logger = get_logger(__name__)

_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "images"
_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

SERVE_PREFIX = "/api/v1/product-info/images"


def save_base64_image(b64_data: str, ext: str = "png") -> str:
    """将 base64 图片保存到本地并返回相对 URL。

    Args:
        b64_data: base64 编码的图片数据（不含 data:image/... 前缀）
        ext: 文件扩展名

    Returns:
        可访问的 URL 路径，如 /api/v1/product-info/images/<uuid>.png
    """
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = _STORAGE_DIR / filename
    filepath.write_bytes(base64.b64decode(b64_data))
    logger.info("Saved image %s (%d bytes)", filename, filepath.stat().st_size)
    return f"{SERVE_PREFIX}/{filename}"


def save_or_passthrough(image_data: str) -> str:
    """若是 base64 则保存并返回 URL，若已是 URL 则直接返回。"""
    if image_data.startswith(("http://", "https://", "/")):
        return image_data
    return save_base64_image(image_data)


def get_image_path(filename: str) -> Path | None:
    """根据文件名返回本地路径（不存在返回 None）。

    对 filename 做路径穿越校验，确保 resolve 后仍在 _STORAGE_DIR 内。
    """
    path = (_STORAGE_DIR / filename).resolve()
    if not path.is_relative_to(_STORAGE_DIR.resolve()):
        return None
    if path.exists() and path.is_file():
        return path
    return None
