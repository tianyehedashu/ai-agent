"""StorageConfigService - 平台对象存储配置 CRUD 与 ImageStore 构建。"""

from __future__ import annotations

import time
from typing import Any
import uuid

from bootstrap.config import settings
from domains.agent.application.ports.image_store_port import ImageStorePort, StorageConfigSnapshot
from domains.agent.domain.listing_studio.storage_config_policy import (
    normalize_storage_type,
    validate_storage_config,
)
from domains.agent.infrastructure.models.system_storage_config import SystemStorageConfig
from domains.agent.infrastructure.repositories.system_storage_config_repository import (
    SystemStorageConfigRepository,
)
from domains.agent.infrastructure.storage.build_image_store import build_image_store
from libs.api.paths import effective_listing_studio_serve_prefix
from libs.crypto import decrypt_value, derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError

_CACHE_TTL_SECONDS = 30

_NO_CONFIG_MESSAGE = "请先在系统管理 → 对象存储完成配置"


class StorageConfigService:
    """平台存储配置服务。"""

    _cached_snapshot: StorageConfigSnapshot | None = None
    _cache_expires_at: float = 0.0

    def __init__(self, repo: SystemStorageConfigRepository) -> None:
        self._repo = repo
        self._encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())

    @classmethod
    def clear_cache(cls) -> None:
        cls._cached_snapshot = None
        cls._cache_expires_at = 0.0

    async def get_active_row(self) -> SystemStorageConfig | None:
        return await self._repo.get_active()

    async def get_active_snapshot(self) -> StorageConfigSnapshot | None:
        now = time.monotonic()
        if self._cached_snapshot is not None and now < self._cache_expires_at:
            return self._cached_snapshot

        row = await self._repo.get_active()
        if row is None:
            return None

        snapshot = self._row_to_snapshot(row)
        type(self)._cached_snapshot = snapshot
        type(self)._cache_expires_at = now + _CACHE_TTL_SECONDS
        return snapshot

    async def require_active_snapshot(self) -> StorageConfigSnapshot:
        snapshot = await self.get_active_snapshot()
        if snapshot is None:
            raise ValidationError(_NO_CONFIG_MESSAGE)
        return snapshot

    async def build_image_store(self) -> ImageStorePort:
        snapshot = await self.require_active_snapshot()
        return build_image_store(snapshot)

    def row_to_admin_dict(self, row: SystemStorageConfig) -> dict[str, Any]:
        """Admin 响应（不含 secret 明文）。"""
        return {
            "storage_type": row.storage_type,
            "local_storage_path": row.local_storage_path,
            "local_serve_prefix": row.local_serve_prefix,
            "s3_bucket": row.s3_bucket,
            "s3_region": row.s3_region,
            "s3_endpoint_url": row.s3_endpoint_url,
            "s3_access_key": row.s3_access_key,
            "s3_public_base_url": row.s3_public_base_url,
            "image_upload_max_bytes": row.image_upload_max_bytes,
            "public_access": row.public_access,
            "is_active": row.is_active,
            "secret_configured": bool(row.s3_secret_key_encrypted),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def upsert_config(
        self,
        *,
        updated_by: uuid.UUID | None,
        storage_type: str,
        local_storage_path: str | None = None,
        local_serve_prefix: str | None = None,
        s3_bucket: str | None = None,
        s3_region: str | None = None,
        s3_endpoint_url: str | None = None,
        s3_access_key: str | None = None,
        s3_secret_key: str | None = None,
        s3_public_base_url: str | None = None,
        image_upload_max_bytes: int = 10_485_760,
        public_access: bool = True,
        is_active: bool = True,
    ) -> SystemStorageConfig:
        existing = await self._repo.get_active()
        secret_encrypted: str | None = None
        if s3_secret_key:
            secret_encrypted = encrypt_value(s3_secret_key, self._encryption_key)
        elif existing and existing.s3_secret_key_encrypted:
            secret_encrypted = existing.s3_secret_key_encrypted

        snapshot = StorageConfigSnapshot(
            storage_type=storage_type,
            local_storage_path=local_storage_path,
            local_serve_prefix=local_serve_prefix,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            s3_endpoint_url=s3_endpoint_url,
            s3_access_key=s3_access_key,
            s3_secret_key=s3_secret_key or (
                decrypt_value(existing.s3_secret_key_encrypted, self._encryption_key)
                if existing and existing.s3_secret_key_encrypted
                else None
            ),
            s3_public_base_url=s3_public_base_url,
            image_upload_max_bytes=image_upload_max_bytes,
            public_access=public_access,
            is_active=is_active,
        )
        validate_storage_config(snapshot)

        row = await self._repo.upsert(
            updated_by=updated_by,
            storage_type=storage_type.strip().lower(),
            local_storage_path=local_storage_path,
            local_serve_prefix=local_serve_prefix,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            s3_endpoint_url=s3_endpoint_url,
            s3_access_key=s3_access_key,
            s3_secret_key_encrypted=secret_encrypted,
            s3_public_base_url=s3_public_base_url,
            image_upload_max_bytes=image_upload_max_bytes,
            public_access=public_access,
            is_active=is_active,
        )
        self.clear_cache()
        return row

    async def test_connection(self) -> dict[str, str]:
        snapshot = await self.require_active_snapshot()
        storage_type = normalize_storage_type(snapshot)
        store = build_image_store(snapshot)
        try:
            await store.test_connection(verify_public=snapshot.public_access)
        except OSError as exc:
            raise ValidationError(str(exc)) from exc
        if storage_type == "local":
            return {"status": "ok", "message": "本地目录可写"}
        bucket = snapshot.s3_bucket or ""
        if snapshot.public_access:
            return {
                "status": "ok",
                "message": f"S3 bucket '{bucket}' 可访问，公开读 URL 正常",
            }
        return {"status": "ok", "message": f"S3 bucket '{bucket}' 可访问"}

    def _row_to_snapshot(self, row: SystemStorageConfig) -> StorageConfigSnapshot:
        secret: str | None = None
        if row.s3_secret_key_encrypted:
            secret = decrypt_value(row.s3_secret_key_encrypted, self._encryption_key)

        return StorageConfigSnapshot(
            storage_type=row.storage_type,
            local_storage_path=row.local_storage_path,
            local_serve_prefix=effective_listing_studio_serve_prefix(row.local_serve_prefix),
            s3_bucket=row.s3_bucket,
            s3_region=row.s3_region,
            s3_endpoint_url=row.s3_endpoint_url,
            s3_access_key=row.s3_access_key,
            s3_secret_key=secret,
            s3_public_base_url=row.s3_public_base_url,
            image_upload_max_bytes=row.image_upload_max_bytes,
            public_access=row.public_access,
            is_active=row.is_active,
        )


__all__ = ["StorageConfigService"]
