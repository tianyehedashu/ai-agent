"""ListingStudioImageService 工厂（后台任务等非 FastAPI 场景复用）。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.application.listing_studio_image_service import ListingStudioImageService
from domains.agent.application.storage_config_service import StorageConfigService
from domains.agent.infrastructure.repositories.system_storage_config_repository import (
    SystemStorageConfigRepository,
)


def create_storage_config_service(db: AsyncSession) -> StorageConfigService:
    return StorageConfigService(SystemStorageConfigRepository(db))


def create_listing_studio_image_service(db: AsyncSession) -> ListingStudioImageService:
    return ListingStudioImageService(create_storage_config_service(db))


__all__ = ["create_listing_studio_image_service", "create_storage_config_service"]
