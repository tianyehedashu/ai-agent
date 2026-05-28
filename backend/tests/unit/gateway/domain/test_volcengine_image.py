"""``volcengine_image`` 域策略纯函数行为。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.policies.volcengine_image import (
    DEFAULT_VOLCENGINE_API_BASE,
    VOLCENGINE_MIN_IMAGE_PIXELS,
    build_volcengine_image_probe_request,
    parse_volcengine_image_endpoint_id,
    resolve_volcengine_image_size,
)


def test_uses_image_endpoint_id_as_model() -> None:
    req = build_volcengine_image_probe_request(
        api_key="sk-test",
        api_base="https://example.com/api/v3",
        image_endpoint_id="ep-image-1",
        size="1920x1920",
    )
    assert req.url == "https://example.com/api/v3/images/generations"
    assert req.auth_header == "Bearer sk-test"
    assert req.json_body["model"] == "ep-image-1"
    assert req.json_body["size"] == "1920x1920"
    assert req.json_body["prompt"] == "ping"
    assert req.json_body["n"] == 1


def test_strips_trailing_slash_from_base() -> None:
    req = build_volcengine_image_probe_request(
        api_key="k",
        api_base="https://example.com/api/v3/",
        image_endpoint_id="ep",
    )
    assert req.url == "https://example.com/api/v3/images/generations"


def test_falls_back_to_default_api_base_when_none() -> None:
    req = build_volcengine_image_probe_request(
        api_key="k",
        api_base=None,
        image_endpoint_id="ep",
    )
    assert req.url.startswith(DEFAULT_VOLCENGINE_API_BASE)
    assert req.url.endswith("/images/generations")


def test_coding_plan_profile_resolves_openai_compat_base() -> None:
    req = build_volcengine_image_probe_request(
        api_key="k",
        api_base="https://ark.cn-beijing.volces.com/api/coding",
        image_endpoint_id="ep",
        profile_id="volcengine.coding_plan",
    )
    assert req.url == "https://ark.cn-beijing.volces.com/api/coding/v3/images/generations"


def test_parse_volcengine_image_endpoint_id() -> None:
    assert parse_volcengine_image_endpoint_id({"image_endpoint_id": " ep-1 "}) == "ep-1"
    assert parse_volcengine_image_endpoint_id({}) is None
    assert parse_volcengine_image_endpoint_id(None) is None


def test_resolve_volcengine_image_size_defaults() -> None:
    assert resolve_volcengine_image_size(None) == "1920x1920"
    assert resolve_volcengine_image_size("  2048x2048  ") == "2048x2048"


def test_resolve_volcengine_image_size_rejects_too_small() -> None:
    with pytest.raises(ValueError, match=str(VOLCENGINE_MIN_IMAGE_PIXELS)):
        resolve_volcengine_image_size("1024x1024")


def test_resolve_volcengine_image_size_rejects_invalid_format() -> None:
    with pytest.raises(ValueError, match="invalid image size"):
        resolve_volcengine_image_size("not-a-size")
