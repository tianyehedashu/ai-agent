"""model_types_tags 单元测试。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.model_types_tags import (
    capability_for_model_type,
    model_types_for_capability_write,
    normalize_model_types,
    primary_capability_from_model_types,
    resolve_catalog_write_capability,
    tags_from_model_types,
    validate_model_types_for_capability,
)
from libs.exceptions import ValidationError


def test_normalize_model_types_dedupes_and_inserts_text() -> None:
    assert normalize_model_types(["image", "text", "image"]) == ("text", "image")


def test_tags_from_model_types_sets_and_clears_vision() -> None:
    out = tags_from_model_types(
        ["text", "image"],
        existing_tags={"supports_vision": False, "display_name": "x"},
        capability="chat",
    )
    assert out["supports_vision"] is True
    assert out["display_name"] == "x"


def test_tags_from_model_types_clears_deselected() -> None:
    out = tags_from_model_types(
        ["text"],
        existing_tags={"supports_vision": True},
        capability="chat",
    )
    assert out["supports_vision"] is False


def test_validate_rejects_image_gen_on_chat_with_separate_capability() -> None:
    with pytest.raises(ValidationError):
        validate_model_types_for_capability(["image_gen"], "chat")


def test_tags_from_model_types_set_only_does_not_clear() -> None:
    out = tags_from_model_types(
        ["image"],
        existing_tags={"supports_image_gen": True},
        capability="chat",
        clear_unselected=False,
    )
    assert out.get("supports_vision") is True
    assert out.get("supports_image_gen") is True


def test_tags_for_model_type_delegates_to_ssot() -> None:
    from domains.gateway.application.personal_models import tags_for_model_type

    assert tags_for_model_type("image") == {"supports_vision": True}
    assert tags_for_model_type("text") == {}


def test_validate_allows_image_gen_on_image_capability() -> None:
    validate_model_types_for_capability(["image_gen"], "image")


def test_primary_capability_from_model_types_prefers_video() -> None:
    assert primary_capability_from_model_types(("text", "video")) == "video_generation"


def test_model_types_for_capability_write_filters_for_image() -> None:
    assert model_types_for_capability_write(("image_gen", "text"), "image") == ("image_gen",)


def test_resolve_catalog_write_capability_falls_back_when_override_invalid() -> None:
    assert (
        resolve_catalog_write_capability(("image_gen",), capability_override="chat") == "image"
    )


def test_capability_for_model_type_mapping() -> None:
    assert capability_for_model_type("image_gen") == "image"
    assert capability_for_model_type("text") == "chat"
