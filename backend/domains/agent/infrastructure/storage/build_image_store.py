"""根据配置快照构建 ImageStore 实现（Infrastructure 适配，不读 DB）。"""

from __future__ import annotations

from pathlib import Path

from domains.agent.application.ports.image_store_port import ImageStorePort, StorageConfigSnapshot
from libs.storage.local_image_store import LocalImageStore
from libs.storage.s3_image_store import S3ImageStore


def build_image_store(snapshot: StorageConfigSnapshot) -> ImageStorePort:
    """由快照构造存储后端（调用方须先通过 domain policy 校验）。"""
    storage_type = snapshot.storage_type.strip().lower()

    if storage_type == "local":
        storage_dir = Path(snapshot.local_storage_path or "./data/storage/images")
        return LocalImageStore(
            storage_dir=storage_dir,
            serve_prefix=snapshot.local_serve_prefix or "/api/v1/listing-studio/images",
            public_base_url=snapshot.s3_public_base_url if snapshot.public_access else None,
        )

    return S3ImageStore(
        bucket=snapshot.s3_bucket or "",
        region=snapshot.s3_region,
        endpoint_url=snapshot.s3_endpoint_url or "",
        access_key=snapshot.s3_access_key or "",
        secret_key=snapshot.s3_secret_key or "",
        public_base_url=snapshot.s3_public_base_url or "",
    )


__all__ = ["build_image_store"]
