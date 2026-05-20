"""Image store port — 对象存储抽象与配置快照。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StorageConfigSnapshot:
    """运行时存储配置快照（含解密后的 secret，仅进程内使用）。"""

    storage_type: str
    image_upload_max_bytes: int = 10_485_760
    public_access: bool = True
    is_active: bool = True
    # local
    local_storage_path: str | None = None
    local_serve_prefix: str | None = "/api/v1/listing-studio/images"
    # s3
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_public_base_url: str | None = None


class ImageStorePort(Protocol):
    """图片持久化端口。"""

    async def save_bytes(
        self,
        content: bytes,
        *,
        ext: str,
        content_type: str | None = None,
    ) -> str:
        """保存二进制图片，返回可访问 URL。"""

    async def persist_image_data(self, image_data: str, *, ext: str = "png") -> str:
        """保存 base64 或透传已有 URL。"""

    def get_local_path(self, filename: str) -> Path | None:
        """本地模式：按文件名解析磁盘路径（非 local 返回 None）。"""

    async def test_connection(self, *, verify_public: bool = True) -> None:
        """验证存储可写；S3 实现可额外校验公开 URL（verify_public=False 时跳过）。"""


__all__ = ["ImageStorePort", "StorageConfigSnapshot"]
