"""``infer_catalog_capability`` 与注册行 ``model_types`` 推导的单元测试。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from bootstrap.config_loader import ModelInfo
from domains.gateway.application.catalog_capability import infer_catalog_capability
from domains.gateway.application.config_catalog_sync import model_types_for_gateway_registration


def _base(**kwargs: object) -> ModelInfo:
    m = ModelInfo(id="m-id", name="M", provider="openai")
    return replace(m, **kwargs)


def test_infer_embedding_from_id() -> None:
    assert infer_catalog_capability(_base(id="text-embedding-3-small")) == "embedding"


def test_infer_image_only_sku() -> None:
    m = _base(
        id="openai/dall-e-3",
        supports_image_gen=True,
        supports_vision=False,
        supports_tools=False,
    )
    assert infer_catalog_capability(m) == "image"


def test_infer_chat_when_multimodal_with_image_gen_flag() -> None:
    """带对话能力的多模态模型不应被标成仅 image 调用面。"""
    m = _base(
        id="gpt-4o",
        supports_image_gen=True,
        supports_vision=True,
        supports_tools=True,
    )
    assert infer_catalog_capability(m) == "chat"


def test_infer_video_generation_only_sku() -> None:
    m = _base(
        id="vendor/video-only",
        supports_video_gen=True,
        supports_vision=False,
        supports_tools=False,
    )
    assert infer_catalog_capability(m) == "video_generation"


def test_model_types_image_capability() -> None:
    tags = {"supports_image_gen": True}
    assert model_types_for_gateway_registration(tags, "image") == ["image_gen"]


def test_model_types_video_generation_capability() -> None:
    tags: dict[str, object] = {}
    assert model_types_for_gateway_registration(tags, "video_generation") == ["video"]


def test_model_types_moderation_empty() -> None:
    assert model_types_for_gateway_registration({"supports_vision": True}, "moderation") == []


@pytest.mark.parametrize(
    ("cap", "expected"),
    [
        ("embedding", []),
        ("rerank", []),
    ],
)
def test_model_types_non_chat_capabilities(cap: str, expected: list[str]) -> None:
    assert model_types_for_gateway_registration({}, cap) == expected
