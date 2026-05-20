"""ListingStudioImageService - 图片上传与生成结果持久化。"""

from __future__ import annotations

from pathlib import Path

from domains.agent.application.storage_config_service import StorageConfigService
from domains.agent.domain.listing_studio.storage_config_policy import is_local_storage
from domains.agent.domain.listing_studio.upload_policy import validate_image_upload


class ListingStudioImageService:
    """Listing Studio 图片存储编排。"""

    def __init__(self, config_service: StorageConfigService) -> None:
        self._config_service = config_service

    async def upload_image(
        self,
        content: bytes,
        content_type: str | None,
    ) -> tuple[str, str, int]:
        """校验并上传用户图片，返回 (url, content_type, size_bytes)。"""
        snapshot = await self._config_service.require_active_snapshot()
        ext = validate_image_upload(
            content_type,
            len(content),
            snapshot.image_upload_max_bytes,
        )
        store = await self._config_service.build_image_store()
        url = await store.save_bytes(content, ext=ext, content_type=content_type)
        return url, content_type or f"image/{ext}", len(content)

    async def persist_generated_image(self, image_data: str, *, ext: str = "png") -> str:
        """持久化生成图片（base64 或已有 URL）。"""
        store = await self._config_service.build_image_store()
        return await store.persist_image_data(image_data, ext=ext)

    async def resolve_local_image_path(self, filename: str) -> Path | None:
        """本地模式：解析可 serv 的文件路径；非 local 或不存在时返回 None。"""
        snapshot = await self._config_service.get_active_snapshot()
        if snapshot is None or not is_local_storage(snapshot):
            return None
        store = await self._config_service.build_image_store()
        return store.get_local_path(filename)


__all__ = ["ListingStudioImageService"]
