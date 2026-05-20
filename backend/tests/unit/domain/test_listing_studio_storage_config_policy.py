"""storage_config_policy 单元测试。"""

import pytest

from domains.agent.application.ports.image_store_port import StorageConfigSnapshot
from domains.agent.domain.listing_studio.storage_config_policy import (
    is_local_storage,
    normalize_storage_type,
    validate_storage_config,
)
from libs.exceptions import ValidationError


def _local_snapshot(**overrides: object) -> StorageConfigSnapshot:
    base = {
        "storage_type": "local",
        "local_storage_path": "./data/storage/images",
        "local_serve_prefix": "/api/v1/listing-studio/images",
        "image_upload_max_bytes": 10_485_760,
        "public_access": True,
        "is_active": True,
    }
    base.update(overrides)
    return StorageConfigSnapshot(**base)  # type: ignore[arg-type]


def _s3_snapshot(**overrides: object) -> StorageConfigSnapshot:
    base = {
        "storage_type": "s3",
        "s3_bucket": "test-bucket",
        "s3_region": "auto",
        "s3_endpoint_url": "https://example.r2.cloudflarestorage.com",
        "s3_access_key": "key",
        "s3_secret_key": "secret",
        "s3_public_base_url": "https://cdn.example.com",
        "image_upload_max_bytes": 10_485_760,
        "public_access": True,
        "is_active": True,
    }
    base.update(overrides)
    return StorageConfigSnapshot(**base)  # type: ignore[arg-type]


@pytest.mark.unit
class TestValidateStorageConfig:
    def test_local_valid(self):
        validate_storage_config(_local_snapshot())

    def test_local_missing_path(self):
        with pytest.raises(ValidationError, match="本地存储路径"):
            validate_storage_config(_local_snapshot(local_storage_path=""))

    def test_s3_valid(self):
        validate_storage_config(_s3_snapshot())

    def test_s3_missing_bucket(self):
        with pytest.raises(ValidationError, match="s3_bucket"):
            validate_storage_config(_s3_snapshot(s3_bucket=None))

    def test_s3_public_requires_base_url(self):
        with pytest.raises(ValidationError, match="s3_public_base_url"):
            validate_storage_config(_s3_snapshot(s3_public_base_url=None))

    def test_invalid_storage_type(self):
        with pytest.raises(ValidationError, match="storage_type"):
            validate_storage_config(_local_snapshot(storage_type="minio"))


@pytest.mark.unit
class TestNormalizeStorageType:
    def test_strips_and_lowercases(self):
        assert normalize_storage_type(_local_snapshot(storage_type="  LOCAL  ")) == "local"

    def test_s3_type(self):
        assert normalize_storage_type(_s3_snapshot()) == "s3"


@pytest.mark.unit
class TestIsLocalStorage:
    def test_local_true(self):
        assert is_local_storage(_local_snapshot()) is True

    def test_s3_false(self):
        assert is_local_storage(_s3_snapshot()) is False
