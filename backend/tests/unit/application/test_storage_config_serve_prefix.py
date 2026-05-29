"""StorageConfigService 本地图片 serve_prefix 与 ROOT_PATH 对齐。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from domains.agent.application.storage_config_service import StorageConfigService
from libs.api.paths import LEGACY_LISTING_STUDIO_IMAGES_PREFIX


def _settings(root_path: str = "", api_prefix: str = "/api/v1") -> SimpleNamespace:
    return SimpleNamespace(root_path=root_path, api_prefix=api_prefix)


@pytest.mark.unit
class TestStorageConfigServePrefix:
    def test_row_to_snapshot_overrides_legacy_default(self) -> None:
        with patch("libs.api.paths.get_settings", return_value=_settings("/ai-agent")):
            row = SimpleNamespace(
                storage_type="local",
                local_storage_path="./data",
                local_serve_prefix=LEGACY_LISTING_STUDIO_IMAGES_PREFIX,
                s3_bucket=None,
                s3_region=None,
                s3_endpoint_url=None,
                s3_access_key=None,
                s3_secret_key_encrypted=None,
                s3_public_base_url=None,
                image_upload_max_bytes=10_485_760,
                public_access=True,
                is_active=True,
            )
            svc = StorageConfigService.__new__(StorageConfigService)
            snapshot = svc._row_to_snapshot(row)
            assert snapshot.local_serve_prefix == "/ai-agent/api/v1/listing-studio/images"

    def test_row_to_snapshot_keeps_custom_prefix(self) -> None:
        with patch("libs.api.paths.get_settings", return_value=_settings("/ai-agent")):
            row = SimpleNamespace(
                storage_type="local",
                local_storage_path="./data",
                local_serve_prefix="/cdn/images",
                s3_bucket=None,
                s3_region=None,
                s3_endpoint_url=None,
                s3_access_key=None,
                s3_secret_key_encrypted=None,
                s3_public_base_url=None,
                image_upload_max_bytes=10_485_760,
                public_access=True,
                is_active=True,
            )
            svc = StorageConfigService.__new__(StorageConfigService)
            snapshot = svc._row_to_snapshot(row)
            assert snapshot.local_serve_prefix == "/cdn/images"
