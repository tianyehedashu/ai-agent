"""listing_studio capability_policy 单测。"""

from domains.agent.domain.listing_studio.capability_policy import (
    merge_model_feature_sources,
    missing_capability_features,
)


def test_merge_prefers_catalog() -> None:
    assert merge_model_feature_sources(
        frozenset({"vision"}),
        frozenset({"text"}),
    ) == frozenset({"vision"})


def test_merge_falls_back_to_static() -> None:
    assert merge_model_feature_sources(None, frozenset({"vision"})) == frozenset({"vision"})


def test_missing_features() -> None:
    assert missing_capability_features(
        frozenset({"vision", "text"}),
        frozenset({"vision"}),
    ) == frozenset({"text"})
