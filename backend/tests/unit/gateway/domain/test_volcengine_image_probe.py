"""``build_volcengine_image_probe_request`` 纯函数行为。"""

from __future__ import annotations

from domains.gateway.domain.policies.volcengine_image_probe import (
    DEFAULT_VOLCENGINE_API_BASE,
    build_volcengine_image_probe_request,
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
        api_key="k", api_base="https://example.com/api/v3/", image_endpoint_id="ep",
    )
    assert req.url == "https://example.com/api/v3/images/generations"


def test_falls_back_to_default_api_base_when_none() -> None:
    req = build_volcengine_image_probe_request(
        api_key="k", api_base=None, image_endpoint_id="ep",
    )
    assert req.url.startswith(DEFAULT_VOLCENGINE_API_BASE)
    assert req.url.endswith("/images/generations")
