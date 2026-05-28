"""S3 兼容对象存储（R2 / OSS / AWS）图片实现。"""

from __future__ import annotations

import base64
import uuid

import aioboto3

from utils.logging import get_logger

logger = get_logger(__name__)

OBJECT_KEY_PREFIX = "images"


class S3ImageStore:
    """S3 兼容图片存储。"""

    def __init__(
        self,
        *,
        bucket: str,
        region: str | None,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        public_base_url: str,
    ) -> None:
        self._bucket = bucket
        self._region = region or "auto"
        self._endpoint_url = endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key
        self._public_base_url = public_base_url.rstrip("/")
        self._session = aioboto3.Session()

    def _object_key(self, ext: str) -> str:
        return f"{OBJECT_KEY_PREFIX}/{uuid.uuid4().hex}.{ext.lstrip('.')}"

    def _public_url(self, key: str) -> str:
        return f"{self._public_base_url}/{key}"

    async def save_bytes(
        self,
        content: bytes,
        *,
        ext: str,
        content_type: str | None = None,
    ) -> str:
        key = self._object_key(ext)

        async with self._session.client(
            "s3",
            region_name=self._region,
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        ) as client:
            put_kwargs: dict[str, str | bytes] = {
                "Bucket": self._bucket,
                "Key": key,
                "Body": content,
            }
            if content_type:
                put_kwargs["ContentType"] = content_type
            await client.put_object(**put_kwargs)
        logger.info("Uploaded S3 object s3://%s/%s (%d bytes)", self._bucket, key, len(content))
        return self._public_url(key)

    async def persist_image_data(self, image_data: str, *, ext: str = "png") -> str:
        if image_data.startswith(("http://", "https://", "/")):
            return image_data
        return await self.save_bytes(base64.b64decode(image_data), ext=ext)

    def get_local_path(self, filename: str) -> None:
        return None

    async def test_connection(self, *, verify_public: bool = True) -> None:
        """验证 bucket 可访问；verify_public 时上传探针并 HEAD 公开 URL。"""
        async with self._session.client(
            "s3",
            region_name=self._region,
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        ) as client:
            await client.head_bucket(Bucket=self._bucket)

            if not verify_public:
                return

            probe_key = f"{OBJECT_KEY_PREFIX}/.connection_probe"
            await client.put_object(
                Bucket=self._bucket,
                Key=probe_key,
                Body=b"ok",
                ContentType="text/plain",
            )
            try:
                import httpx  # pylint: disable=import-outside-toplevel

                probe_url = self._public_url(probe_key)
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http:
                    response = await http.head(probe_url)
                    if response.status_code >= 400:
                        raise OSError(f"公开 URL 不可访问 ({response.status_code}): {probe_url}")
            finally:
                await client.delete_object(Bucket=self._bucket, Key=probe_key)


__all__ = ["OBJECT_KEY_PREFIX", "S3ImageStore"]
