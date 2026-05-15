"""``allowed_capabilities_from_storage`` 单元测试。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.types import (
    GatewayCapability,
    allowed_capabilities_from_storage,
)


def test_empty_and_whitespace() -> None:
    assert allowed_capabilities_from_storage(None) == ()
    assert allowed_capabilities_from_storage([]) == ()
    assert allowed_capabilities_from_storage(["", "  ", "chat"]) == (GatewayCapability.CHAT,)


def test_valid_list() -> None:
    caps = allowed_capabilities_from_storage(["chat", "embedding"])
    assert caps == (GatewayCapability.CHAT, GatewayCapability.EMBEDDING)
    caps2 = allowed_capabilities_from_storage(
        ["video_generation", "moderation", "image"],
    )
    assert caps2 == (
        GatewayCapability.VIDEO_GENERATION,
        GatewayCapability.MODERATION,
        GatewayCapability.IMAGE,
    )


def test_invalid_raises() -> None:
    with pytest.raises(ValueError, match="invalid gateway capability"):
        allowed_capabilities_from_storage(["not_a_capability"])
