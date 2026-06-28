"""proxy_vision_image_urls 单元测试。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domains.agent.application.listing_studio_image_service import ListingStudioImageService
from domains.agent.application.listing_studio_local_image_for_gateway import (
    AgentListingStudioLocalImagePort,
)
from domains.agent.application.ports.image_store_port import StorageConfigSnapshot
from domains.gateway.application.proxy.proxy_vision_image_urls import (
    inline_vision_image_urls_in_kwargs,
    inline_vision_image_urls_in_messages,
)
from libs.storage.local_image_store import LocalImageStore


def _local_snapshot(storage_path: str) -> StorageConfigSnapshot:
    return StorageConfigSnapshot(
        storage_type="local",
        local_storage_path=storage_path,
        local_serve_prefix="/api/v1/listing-studio/images",
        image_upload_max_bytes=10_485_760,
        public_access=False,
        is_active=True,
    )


@pytest.mark.unit
class TestInlineVisionImageUrlsInMessages:
    @pytest.mark.asyncio
    async def test_inlines_relative_listing_studio_url(self, tmp_path: Path) -> None:
        storage_dir = tmp_path / "images"
        storage_dir.mkdir()
        (storage_dir / "abc.png").write_bytes(b"\x89PNG")

        store = LocalImageStore(storage_dir=storage_dir)
        config_svc = MagicMock()
        config_svc.get_active_snapshot = AsyncMock(return_value=_local_snapshot(str(storage_dir)))
        config_svc.build_image_store = AsyncMock(return_value=store)
        session = MagicMock()
        with patch(
            "domains.agent.application.listing_studio_local_image_for_gateway.create_listing_studio_image_service",
            return_value=ListingStudioImageService(config_svc),
        ):
            image_port = AgentListingStudioLocalImagePort(session)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "/api/v1/listing-studio/images/abc.png",
                            },
                        },
                    ],
                }
            ]
            out = await inline_vision_image_urls_in_messages(messages, image_port)
        url = out[0]["content"][1]["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_leaves_public_https_unchanged(self) -> None:
        image_port = MagicMock()
        image_port.resolve_local_image_path = AsyncMock(return_value=None)

        original = "https://cdn.example.com/photo.jpg"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": original}},
                ],
            }
        ]
        out = await inline_vision_image_urls_in_messages(messages, image_port)
        assert out[0]["content"][0]["image_url"]["url"] == original
        image_port.resolve_local_image_path.assert_not_called()


@pytest.mark.unit
class TestInlineVisionImageUrlsInKwargs:
    @pytest.mark.asyncio
    async def test_no_messages_passthrough(self) -> None:
        kwargs = {"model": "gpt-4"}
        port = MagicMock()
        assert await inline_vision_image_urls_in_kwargs(kwargs, image_port=port) == kwargs

    @pytest.mark.asyncio
    async def test_uses_isolated_session_when_port_omitted(self) -> None:
        port = MagicMock()
        port.resolve_local_image_path = AsyncMock(return_value=None)
        isolated = MagicMock()
        # 必须含 image_url part，才会绕过 `_messages_have_image_url_parts` 早返、进入 session 分支
        kwargs = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "/api/v1/listing-studio/images/x.png"},
                        },
                    ],
                }
            ]
        }

        class _SessionCtx:
            async def __aenter__(self) -> MagicMock:
                return isolated

            async def __aexit__(self, *_args: object) -> None:
                return None

        with (
            patch(
                "domains.gateway.application.proxy.proxy_vision_image_urls.get_session_context",
                return_value=_SessionCtx(),
            ),
            patch(
                "domains.gateway.application.proxy.proxy_vision_image_urls.get_listing_studio_local_image_port",
                return_value=port,
            ) as get_port,
        ):
            await inline_vision_image_urls_in_kwargs(kwargs)

        get_port.assert_called_once_with(isolated)

    @pytest.mark.asyncio
    async def test_short_circuits_without_image_url_parts(self) -> None:
        """messages 中无 ``type=="image_url"`` part 时，不应创建 session / 查 image_port。"""
        kwargs = {
            "messages": [
                {"role": "system", "content": "hi"},
                {"role": "user", "content": [{"type": "text", "text": "plain"}]},
            ]
        }
        with (
            patch(
                "domains.gateway.application.proxy.proxy_vision_image_urls.get_session_context",
            ) as get_session,
            patch(
                "domains.gateway.application.proxy.proxy_vision_image_urls.get_listing_studio_local_image_port",
            ) as get_port,
        ):
            result = await inline_vision_image_urls_in_kwargs(kwargs)

        assert result is kwargs  # 原对象返回，零拷贝
        get_session.assert_not_called()
        get_port.assert_not_called()
