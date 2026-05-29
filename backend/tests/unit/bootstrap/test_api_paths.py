"""api paths 单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from libs.api.paths import (
    LEGACY_LISTING_STUDIO_IMAGES_PREFIX,
    anthropic_compat_base,
    api_v1_path,
    effective_listing_studio_serve_prefix,
    listing_studio_images_serve_prefix,
    openai_compat_base,
    public_api_url,
    service_path,
)


def _settings(root_path: str = "", api_prefix: str = "/api/v1") -> SimpleNamespace:
    return SimpleNamespace(root_path=root_path, api_prefix=api_prefix)


class TestApiPaths:
    def test_default_paths_without_root(self) -> None:
        with patch("libs.api.paths.get_settings", return_value=_settings()):
            assert service_path() == "/"
            assert service_path("health") == "/health"
            assert api_v1_path() == "/api/v1"
            assert api_v1_path("gateway") == "/api/v1/gateway"
            assert openai_compat_base() == "/api/v1/openai/v1"
            assert anthropic_compat_base() == "/api/v1/anthropic"
            assert listing_studio_images_serve_prefix() == "/api/v1/listing-studio/images"

    def test_default_root_path(self) -> None:
        with patch("libs.api.paths.get_settings", return_value=_settings("/ai-agent")):
            assert service_path("health") == "/ai-agent/health"
            assert api_v1_path() == "/ai-agent/api/v1"
            assert openai_compat_base() == "/ai-agent/api/v1/openai/v1"

    def test_paths_without_root_prefix(self) -> None:
        with patch("libs.api.paths.get_settings", return_value=_settings()):
            assert api_v1_path("gateway", "teams") == "/api/v1/gateway/teams"
            assert anthropic_compat_base() == "/api/v1/anthropic"

    def test_normalizes_duplicate_slashes(self) -> None:
        with patch(
            "libs.api.paths.get_settings",
            return_value=_settings("/ai-agent/", "/api/v1/"),
        ):
            assert api_v1_path("/gateway/") == "/ai-agent/api/v1/gateway"

    def test_public_api_url(self) -> None:
        with patch("libs.api.paths.get_settings", return_value=_settings()):
            assert public_api_url("http://localhost:8000", "mcp", "llm-server") == (
                "http://localhost:8000/api/v1/mcp/llm-server"
            )

    def test_effective_listing_studio_serve_prefix(self) -> None:
        with patch("libs.api.paths.get_settings", return_value=_settings("/ai-agent")):
            assert effective_listing_studio_serve_prefix(None) == (
                "/ai-agent/api/v1/listing-studio/images"
            )
            assert (
                effective_listing_studio_serve_prefix(LEGACY_LISTING_STUDIO_IMAGES_PREFIX)
                == "/ai-agent/api/v1/listing-studio/images"
            )
            assert effective_listing_studio_serve_prefix("/custom/prefix") == "/custom/prefix"
