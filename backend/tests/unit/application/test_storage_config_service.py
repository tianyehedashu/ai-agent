"""StorageConfigService 单元测试。"""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.agent.application.storage_config_service import StorageConfigService
from domains.agent.infrastructure.models.system_storage_config import SystemStorageConfig
from libs.exceptions import ValidationError


def _local_row() -> SystemStorageConfig:
    row = SystemStorageConfig(
        id=uuid.uuid4(),
        storage_type="local",
        local_storage_path="./data/storage/images",
        local_serve_prefix="/api/v1/listing-studio/images",
        image_upload_max_bytes=10_485_760,
        public_access=True,
        is_active=True,
    )
    return row


@pytest.mark.unit
class TestStorageConfigService:
    @pytest.mark.asyncio
    async def test_require_active_snapshot_raises_when_missing(self):
        repo = MagicMock()
        repo.get_active = AsyncMock(return_value=None)
        svc = StorageConfigService(repo)
        with pytest.raises(ValidationError, match="对象存储"):
            await svc.require_active_snapshot()

    @pytest.mark.asyncio
    async def test_get_active_snapshot_caches(self):
        repo = MagicMock()
        row = _local_row()
        repo.get_active = AsyncMock(return_value=row)
        svc = StorageConfigService(repo)

        first = await svc.get_active_snapshot()
        second = await svc.get_active_snapshot()
        assert first is not None
        assert first.storage_type == "local"
        assert second is first
        assert repo.get_active.await_count == 1

        StorageConfigService.clear_cache()
        await svc.get_active_snapshot()
        assert repo.get_active.await_count == 2

    @pytest.mark.asyncio
    async def test_upsert_validates_local_config(self):
        repo = MagicMock()
        repo.get_active = AsyncMock(return_value=None)
        repo.upsert = AsyncMock(return_value=_local_row())
        svc = StorageConfigService(repo)

        await svc.upsert_config(
            updated_by=None,
            storage_type="local",
            local_storage_path="./data/storage/images",
            local_serve_prefix="/api/v1/listing-studio/images",
        )
        repo.upsert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upsert_rejects_incomplete_s3(self):
        repo = MagicMock()
        repo.get_active = AsyncMock(return_value=None)
        svc = StorageConfigService(repo)

        with pytest.raises(ValidationError, match="S3 模式缺少必填字段"):
            await svc.upsert_config(
                updated_by=None,
                storage_type="s3",
                s3_bucket="b",
            )

    @pytest.mark.asyncio
    async def test_test_connection_local(self, tmp_path):
        repo = MagicMock()
        repo.db.in_transaction.return_value = False
        row = _local_row()
        row.local_storage_path = str(tmp_path / "images")
        repo.get_active = AsyncMock(return_value=row)
        svc = StorageConfigService(repo)

        result = await svc.test_connection()
        assert result["status"] == "ok"
        assert "本地" in result["message"]

    @pytest.mark.asyncio
    async def test_test_connection_s3_skips_public_when_disabled(self):
        repo = MagicMock()
        repo.db.in_transaction.return_value = False
        row = SystemStorageConfig(
            id=uuid.uuid4(),
            storage_type="s3",
            s3_bucket="b",
            s3_region="auto",
            s3_endpoint_url="https://example.com",
            s3_access_key="ak",
            s3_secret_key_encrypted=None,
            s3_public_base_url=None,
            image_upload_max_bytes=10_485_760,
            public_access=False,
            is_active=True,
        )
        repo.get_active = AsyncMock(return_value=row)
        svc = StorageConfigService(repo)

        mock_store = MagicMock()
        mock_store.test_connection = AsyncMock()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "domains.agent.application.storage_config_service.build_image_store",
                lambda _snap: mock_store,
            )
            result = await svc.test_connection()

        mock_store.test_connection.assert_awaited_once_with(verify_public=False)
        assert result["status"] == "ok"
        assert "b" in result["message"]
