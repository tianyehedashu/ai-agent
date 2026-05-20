"""LocalImageStore 单元测试。"""

from pathlib import Path

import pytest

from libs.storage.local_image_store import LocalImageStore


@pytest.mark.unit
class TestLocalImageStore:
    @pytest.mark.asyncio
    async def test_save_bytes_returns_serve_url(self, tmp_path: Path):
        store = LocalImageStore(tmp_path, serve_prefix="/api/v1/listing-studio/images")
        url = await store.save_bytes(b"fake-png", ext="png", content_type="image/png")
        assert url.startswith("/api/v1/listing-studio/images/")
        assert url.endswith(".png")

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path: Path):
        store = LocalImageStore(tmp_path)
        await store.save_bytes(b"x", ext="png")
        assert store.get_local_path("../etc/passwd") is None
        assert store.get_local_path("../../outside.png") is None

    @pytest.mark.asyncio
    async def test_persist_passthrough_url(self, tmp_path: Path):
        store = LocalImageStore(tmp_path)
        url = await store.persist_image_data("https://cdn.example.com/a.png")
        assert url == "https://cdn.example.com/a.png"
