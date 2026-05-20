"""Admin Storage API - 平台对象存储配置。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from domains.agent.application.storage_config_service import StorageConfigService
from domains.agent.presentation.schemas.admin_storage import (
    StorageConfigAdminResponse,
    StorageTestResponse,
    UpdateStorageConfigBody,
)
from domains.identity.presentation.deps import AdminUser
from libs.api.deps import get_storage_config_service
from libs.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=StorageConfigAdminResponse)
async def get_storage_config(
    _: AdminUser,
    service: StorageConfigService = Depends(get_storage_config_service),
) -> StorageConfigAdminResponse:
    row = await service.get_active_row()
    if row is None:
        raise NotFoundError("SystemStorageConfig", "active")
    return StorageConfigAdminResponse(**service.row_to_admin_dict(row))


@router.put("", response_model=StorageConfigAdminResponse)
async def update_storage_config(
    body: UpdateStorageConfigBody,
    admin: AdminUser,
    service: StorageConfigService = Depends(get_storage_config_service),
) -> StorageConfigAdminResponse:
    row = await service.upsert_config(
        updated_by=uuid.UUID(admin.id),
        storage_type=body.storage_type,
        local_storage_path=body.local_storage_path,
        local_serve_prefix=body.local_serve_prefix,
        s3_bucket=body.s3_bucket,
        s3_region=body.s3_region,
        s3_endpoint_url=body.s3_endpoint_url,
        s3_access_key=body.s3_access_key,
        s3_secret_key=body.s3_secret_key,
        s3_public_base_url=body.s3_public_base_url,
        image_upload_max_bytes=body.image_upload_max_bytes,
        public_access=body.public_access,
        is_active=body.is_active,
    )
    return StorageConfigAdminResponse(**service.row_to_admin_dict(row))


@router.post("/test", response_model=StorageTestResponse, status_code=status.HTTP_200_OK)
async def test_storage_connection(
    _: AdminUser,
    service: StorageConfigService = Depends(get_storage_config_service),
) -> StorageTestResponse:
    result = await service.test_connection()
    return StorageTestResponse(**result)


__all__ = ["router"]
