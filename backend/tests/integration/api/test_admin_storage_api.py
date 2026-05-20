"""Admin Storage API 集成测试。"""

from fastapi import status
from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestAdminStorageApi:
    @pytest.mark.asyncio
    async def test_get_requires_admin(
        self,
        dev_client: AsyncClient,
        auth_headers: dict,
    ):
        r = await dev_client.get("/api/v1/admin/storage", headers=auth_headers)
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_succeeds_for_admin(
        self,
        dev_client: AsyncClient,
        admin_headers: dict,
    ):
        r = await dev_client.get("/api/v1/admin/storage", headers=admin_headers)
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        assert data["storage_type"] in {"local", "s3"}
        assert "image_upload_max_bytes" in data
        assert "secret_configured" in data

    @pytest.mark.asyncio
    async def test_update_local_config(
        self,
        dev_client: AsyncClient,
        admin_headers: dict,
    ):
        r = await dev_client.put(
            "/api/v1/admin/storage",
            headers=admin_headers,
            json={
                "storage_type": "local",
                "local_storage_path": "./data/storage/images",
                "local_serve_prefix": "/api/v1/listing-studio/images",
                "image_upload_max_bytes": 10485760,
                "public_access": True,
                "is_active": True,
            },
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["storage_type"] == "local"

    @pytest.mark.asyncio
    async def test_test_connection_admin(
        self,
        dev_client: AsyncClient,
        admin_headers: dict,
    ):
        r = await dev_client.post(
            "/api/v1/admin/storage/test",
            headers=admin_headers,
            json={},
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["status"] == "ok"
