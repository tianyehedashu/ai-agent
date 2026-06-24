"""Agnes 伪兼容生图请求构建（纯函数）。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.policies.agnes_image import (
    AGNES_DEFAULT_RESPONSE_FORMAT,
    build_agnes_image_request,
    extract_agnes_image_inputs,
    should_use_agnes_direct_image,
)


@pytest.mark.parametrize(
    ("provider", "expected"),
    [("agnes", True), ("Agnes", True), (" agnes ", True), ("openai", False), ("volcengine", False)],
)
def test_should_use_agnes_direct_image(provider: str, expected: bool) -> None:
    assert should_use_agnes_direct_image(provider) is expected


def test_extract_inputs_prefers_top_level_then_extra_body() -> None:
    assert extract_agnes_image_inputs({"image": ["https://a.png", " "]}) == ["https://a.png"]
    assert extract_agnes_image_inputs({"image": "https://b.png"}) == ["https://b.png"]
    assert extract_agnes_image_inputs({"extra_body": {"image": ["https://c.png"]}}) == [
        "https://c.png"
    ]
    assert extract_agnes_image_inputs({}) == []


def test_text2img_uses_profile_default_base_and_wraps_response_format() -> None:
    """文生图：无 api_base 回落 profile 默认根；response_format 进字面量 extra_body。"""
    req = build_agnes_image_request(
        api_key="sk-x",
        api_base=None,
        model="agnes-image-2.0-flash",
        prompt="a cat",
    )
    assert req.url == "https://apihub.agnes-ai.com/v1/images/generations"
    assert req.auth_header == "Bearer sk-x"
    assert req.json_body["model"] == "agnes-image-2.0-flash"
    assert req.json_body["prompt"] == "a cat"
    assert req.json_body["extra_body"] == {"response_format": AGNES_DEFAULT_RESPONSE_FORMAT}
    # 文生图不带 image，也不应自动加 img2img tag
    assert "image" not in req.json_body["extra_body"]
    assert "tags" not in req.json_body


def test_img2img_wraps_image_into_extra_body_and_adds_tag() -> None:
    """图生图：image 进字面量 extra_body，自动补 tags=[img2img]。"""
    req = build_agnes_image_request(
        api_key="sk-x",
        api_base="https://apihub.agnes-ai.com/v1",
        model="agnes-image-2.0-flash",
        prompt="make it night",
        size="1792x1024",
        n=2,
        seed=7,
        images=["https://in1.png", "https://in2.png"],
        response_format="url",
    )
    body = req.json_body
    assert body["size"] == "1792x1024"
    assert body["n"] == 2
    assert body["seed"] == 7
    assert body["tags"] == ["img2img"]
    assert body["extra_body"] == {
        "response_format": "url",
        "image": ["https://in1.png", "https://in2.png"],
    }


def test_explicit_tags_are_respected() -> None:
    req = build_agnes_image_request(
        api_key="sk-x",
        api_base=None,
        model="agnes-image-2.0-flash",
        prompt="compose",
        images=["https://in1.png"],
        tags=["custom-tag"],
    )
    assert req.json_body["tags"] == ["custom-tag"]


def test_blank_prompt_rejected() -> None:
    with pytest.raises(ValueError, match="prompt is required"):
        build_agnes_image_request(
            api_key="sk-x",
            api_base=None,
            model="agnes-image-2.0-flash",
            prompt="   ",
        )
