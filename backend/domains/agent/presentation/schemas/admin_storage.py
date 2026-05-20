"""Admin Storage API schemas。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StorageConfigAdminResponse(BaseModel):
    storage_type: str
    local_storage_path: str | None = None
    local_serve_prefix: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_public_base_url: str | None = None
    image_upload_max_bytes: int
    public_access: bool
    is_active: bool
    secret_configured: bool
    updated_at: str | None = None


class UpdateStorageConfigBody(BaseModel):
    storage_type: str = Field(..., description="local | s3")
    local_storage_path: str | None = None
    local_serve_prefix: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = Field(
        None,
        description="留空表示不修改已有 secret",
    )
    s3_public_base_url: str | None = None
    image_upload_max_bytes: int = Field(10_485_760, ge=1)
    public_access: bool = True
    is_active: bool = True


class StorageTestResponse(BaseModel):
    status: str
    message: str


__all__ = [
    "StorageConfigAdminResponse",
    "StorageTestResponse",
    "UpdateStorageConfigBody",
]
