"""对象存储配置校验策略（纯函数）。"""

from __future__ import annotations

from typing import Protocol

from libs.exceptions import ValidationError


class StorageConfigLike(Protocol):
    """存储配置校验所需字段（与 StorageConfigSnapshot 对齐）。"""

    storage_type: str
    image_upload_max_bytes: int
    local_storage_path: str | None
    local_serve_prefix: str | None
    s3_bucket: str | None
    s3_endpoint_url: str | None
    s3_access_key: str | None
    s3_secret_key: str | None
    s3_public_base_url: str | None
    public_access: bool


def validate_storage_config(snapshot: StorageConfigLike) -> None:
    """校验存储配置快照是否可用于读写。

    Raises:
        ValidationError: 配置不完整或非法
    """
    storage_type = snapshot.storage_type.strip().lower()
    if storage_type not in {"local", "s3"}:
        raise ValidationError(
            "storage_type 必须为 local 或 s3",
            details={"field": "storage_type"},
        )

    if snapshot.image_upload_max_bytes <= 0:
        raise ValidationError(
            "image_upload_max_bytes 必须大于 0",
            details={"field": "image_upload_max_bytes"},
        )

    if storage_type == "local":
        if not snapshot.local_storage_path or not snapshot.local_storage_path.strip():
            raise ValidationError(
                "本地存储路径不能为空",
                details={"field": "local_storage_path"},
            )
        if not snapshot.local_serve_prefix or not snapshot.local_serve_prefix.strip():
            raise ValidationError(
                "本地访问前缀不能为空",
                details={"field": "local_serve_prefix"},
            )
        return

    missing: list[str] = []
    if not snapshot.s3_bucket:
        missing.append("s3_bucket")
    if not snapshot.s3_endpoint_url:
        missing.append("s3_endpoint_url")
    if not snapshot.s3_access_key:
        missing.append("s3_access_key")
    if not snapshot.s3_secret_key:
        missing.append("s3_secret_key")
    if snapshot.public_access and not snapshot.s3_public_base_url:
        missing.append("s3_public_base_url")

    if missing:
        raise ValidationError(
            f"S3 模式缺少必填字段: {', '.join(missing)}",
            details={"field": missing[0]},
        )


def normalize_storage_type(snapshot: StorageConfigLike) -> str:
    """返回规范化 storage_type（小写、去空白）。"""
    return snapshot.storage_type.strip().lower()


def is_local_storage(snapshot: StorageConfigLike) -> bool:
    """当前配置是否为本地存储模式。"""
    return normalize_storage_type(snapshot) == "local"


__all__ = [
    "StorageConfigLike",
    "is_local_storage",
    "normalize_storage_type",
    "validate_storage_config",
]
