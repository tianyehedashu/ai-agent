"""CatalogSeedModel.features 属性测试。"""

import pytest

from domains.gateway.domain.catalog_seed_model import CatalogSeedModel


@pytest.mark.unit
class TestCatalogSeedModelFeatures:
    def test_features_empty_when_all_false(self) -> None:
        info = CatalogSeedModel(
            id="test",
            name="Test",
            provider="test",
            supports_vision=False,
            supports_tools=False,
            supports_reasoning=False,
            supports_json_mode=False,
        )
        assert info.features == frozenset()

    def test_features_vision_when_supports_vision(self) -> None:
        info = CatalogSeedModel(
            id="vl",
            name="Vision",
            provider="test",
            supports_vision=True,
        )
        assert "vision" in info.features

    def test_features_combined(self) -> None:
        info = CatalogSeedModel(
            id="full",
            name="Full",
            provider="test",
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
        )
        assert info.features == frozenset({"vision", "tools", "json_mode"})
