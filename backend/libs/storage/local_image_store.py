"""
Local Image Store - 本地图片存储

实现 ImageStorePort，将图片保存到本地目录并返回可访问 URL。
"""

from __future__ import annotations

import base64
from pathlib import Path
import uuid

from utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SERVE_PREFIX = "/api/v1/listing-studio/images"


class LocalImageStore:
    """本地文件系统图片存储。"""

    def __init__(
        self,
        storage_dir: Path,
        serve_prefix: str = DEFAULT_SERVE_PREFIX,
        public_base_url: str | None = None,
    ) -> None:
        self._storage_dir = storage_dir
        self._serve_prefix = serve_prefix.rstrip("/")
        self._public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    @property
    def storage_dir(self) -> Path:
        return self._storage_dir

    def _build_url(self, filename: str) -> str:
        path = f"{self._serve_prefix}/{filename}"
        if self._public_base_url:
            return f"{self._public_base_url}{path}"
        return path

    async def save_bytes(
        self,
        content: bytes,
        *,
        ext: str,
        content_type: str | None = None,
    ) -> str:
        filename = f"{uuid.uuid4().hex}.{ext.lstrip('.')}"
        filepath = self._storage_dir / filename
        filepath.write_bytes(content)
        logger.info("Saved local image %s (%d bytes)", filename, len(content))
        return self._build_url(filename)

    async def persist_image_data(self, image_data: str, *, ext: str = "png") -> str:
        if image_data.startswith(("http://", "https://", "/")):
            return image_data
        return await self.save_bytes(base64.b64decode(image_data), ext=ext)

    def get_local_path(self, filename: str) -> Path | None:
        path = (self._storage_dir / filename).resolve()
        if not path.is_relative_to(self._storage_dir.resolve()):
            return None
        if path.exists() and path.is_file():
            return path
        return None

    async def test_connection(self, *, verify_public: bool = True) -> None:
        del verify_public
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        probe = self._storage_dir / ".write_probe"
        try:
            probe.write_text("ok", encoding="utf-8")
        except OSError as exc:
            raise OSError(f"本地目录不可写: {self._storage_dir}") from exc
        probe.unlink(missing_ok=True)


def get_image_path(storage_dir: Path, filename: str) -> Path | None:
    """模块级辅助：路径穿越安全校验。"""
    store = LocalImageStore(storage_dir)
    return store.get_local_path(filename)


__all__ = [
    "DEFAULT_SERVE_PREFIX",
    "LocalImageStore",
    "get_image_path",
]
