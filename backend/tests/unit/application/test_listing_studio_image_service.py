"""ListingStudioImageService 单元测试。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from domains.agent.application.listing_studio_image_service import ListingStudioImageService
from domains.agent.application.ports.image_store_port import StorageConfigSnapshot
from libs.storage.local_image_store import LocalImageStore


def _local_snapshot() -> StorageConfigSnapshot:
    return StorageConfigSnapshot(
        storage_type="local",
        local_storage_path="./data/storage/images",
        local_serve_prefix="/api/v1/listing-studio/images",
        image_upload_max_bytes=10_485_760,
        public_access=True,
        is_active=True,
    )


@pytest.mark.unit
class TestListingStudioImageServiceResolveLocalPath:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_active_config(self, tmp_path: Path):
        config_svc = MagicMock()
        config_svc.get_active_snapshot = AsyncMock(return_value=None)
        svc = ListingStudioImageService(config_svc)

        assert await svc.resolve_local_image_path("test.png") is None

    @pytest.mark.asyncio
    async def test_returns_none_for_s3_mode(self):
        config_svc = MagicMock()
        config_svc.get_active_snapshot = AsyncMock(
            return_value=StorageConfigSnapshot(
                storage_type="s3",
                s3_bucket="b",
                s3_endpoint_url="https://example.com",
                s3_access_key="k",
                s3_secret_key="s",
                s3_public_base_url="https://cdn.example.com",
                image_upload_max_bytes=10_485_760,
                public_access=True,
                is_active=True,
            )
        )
        svc = ListingStudioImageService(config_svc)

        assert await svc.resolve_local_image_path("test.png") is None
        config_svc.build_image_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_path_when_file_exists(self, tmp_path: Path):
        storage_dir = tmp_path / "images"
        storage_dir.mkdir()
        (storage_dir / "abc.png").write_bytes(b"png")

        store = LocalImageStore(storage_dir=storage_dir)
        config_svc = MagicMock()
        config_svc.get_active_snapshot = AsyncMock(return_value=_local_snapshot())
        config_svc.build_image_store = AsyncMock(return_value=store)
        svc = ListingStudioImageService(config_svc)

        path = await svc.resolve_local_image_path("abc.png")
        assert path is not None
        assert path.name == "abc.png"
        assert path.read_bytes() == b"png"

    @pytest.mark.asyncio
    async def test_rejects_path_traversal(self, tmp_path: Path):
        storage_dir = tmp_path / "images"
        storage_dir.mkdir()

        store = LocalImageStore(storage_dir=storage_dir)
        config_svc = MagicMock()
        config_svc.get_active_snapshot = AsyncMock(return_value=_local_snapshot())
        config_svc.build_image_store = AsyncMock(return_value=store)
        svc = ListingStudioImageService(config_svc)

        assert await svc.resolve_local_image_path("../secret.txt") is None
