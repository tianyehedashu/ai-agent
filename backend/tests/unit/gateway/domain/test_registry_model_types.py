"""``registry_model_types`` 推导与列表筛选匹配。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.catalog.model_list_policy import parse_registry_ability_filter
from domains.gateway.domain.catalog.registry_model_types import (
    ability_filters_via_sql_capability_column,
    infer_model_types_from_tags,
    matches_registry_ability_filter,
)
from libs.exceptions import ValidationError


def test_chat_with_vision_matches_image_and_text_filters() -> None:
    tags = {"supports_vision": True}
    cap = "chat"
    assert matches_registry_ability_filter(tags=tags, capability=cap, filter_value="image")
    assert matches_registry_ability_filter(tags=tags, capability=cap, filter_value="text")
    assert not matches_registry_ability_filter(tags=tags, capability=cap, filter_value="embedding")


def test_embedding_sql_capability_only() -> None:
    assert ability_filters_via_sql_capability_column("embedding")
    assert not ability_filters_via_sql_capability_column("image")


def test_parse_registry_ability_filter_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        parse_registry_ability_filter("not-a-capability")


def test_infer_model_types_moderation_empty() -> None:
    assert infer_model_types_from_tags({"supports_vision": True}, "moderation") == []
