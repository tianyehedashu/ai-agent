"""S3ImageStore 单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.storage.s3_image_store import S3ImageStore


@pytest.mark.unit
class TestS3ImageStore:
    @pytest.mark.asyncio
    async def test_save_bytes_uploads_and_returns_public_url(self):
        store = S3ImageStore(
            bucket="my-bucket",
            region="auto",
            endpoint_url="https://example.r2.cloudflarestorage.com",
            access_key="ak",
            secret_key="sk",
            public_base_url="https://cdn.example.com",
        )

        mock_client = AsyncMock()
        mock_client.put_object = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.client.return_value = mock_cm

        with patch.object(store, "_session", mock_session):
            url = await store.save_bytes(b"img", ext="png", content_type="image/png")

        assert url.startswith("https://cdn.example.com/images/")
        assert url.endswith(".png")
        mock_client.put_object.assert_awaited_once()
        call_kwargs = mock_client.put_object.await_args.kwargs
        assert call_kwargs["Bucket"] == "my-bucket"
        assert call_kwargs["Key"].startswith("images/")
        assert call_kwargs["ContentType"] == "image/png"

    @pytest.mark.asyncio
    async def test_test_connection_head_bucket_only(self):
        store = S3ImageStore(
            bucket="my-bucket",
            region="auto",
            endpoint_url="https://example.r2.cloudflarestorage.com",
            access_key="ak",
            secret_key="sk",
            public_base_url="https://cdn.example.com",
        )

        mock_client = AsyncMock()
        mock_client.head_bucket = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.client.return_value = mock_cm

        with patch.object(store, "_session", mock_session):
            await store.test_connection(verify_public=False)

        mock_client.head_bucket.assert_awaited_once_with(Bucket="my-bucket")
        mock_client.put_object.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_test_connection_probes_public_url(self):
        store = S3ImageStore(
            bucket="my-bucket",
            region="auto",
            endpoint_url="https://example.r2.cloudflarestorage.com",
            access_key="ak",
            secret_key="sk",
            public_base_url="https://cdn.example.com",
        )

        mock_client = AsyncMock()
        mock_client.head_bucket = AsyncMock()
        mock_client.put_object = AsyncMock()
        mock_client.delete_object = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.client.return_value = mock_cm

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.head = AsyncMock(return_value=MagicMock(status_code=200))

        with (
            patch.object(store, "_session", mock_session),
            patch("httpx.AsyncClient", return_value=mock_http),
        ):
            await store.test_connection(verify_public=True)

        mock_client.put_object.assert_awaited_once()
        mock_client.delete_object.assert_awaited_once()
        mock_http.head.assert_awaited_once()
