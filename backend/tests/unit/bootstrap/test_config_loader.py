"""
Config Loader 单元测试 - ModelInfo.features
"""

import pytest

from bootstrap.config_loader import ModelInfo


@pytest.mark.unit
class TestModelInfoFeatures:
    """ModelInfo.features 属性测试"""

    def test_features_empty_when_all_false(self):
        """测试: 所有能力为 False 时 features 为空"""
        info = ModelInfo(
            id="test",
            name="Test",
            provider="test",
            supports_vision=False,
            supports_tools=False,
            supports_reasoning=False,
            supports_json_mode=False,
        )
        assert info.features == frozenset()

    def test_features_vision_when_supports_vision(self):
        """测试: supports_vision=True 时包含 vision"""
        info = ModelInfo(
            id="vl",
            name="Vision",
            provider="test",
            supports_vision=True,
        )
        assert "vision" in info.features

    def test_features_tools_when_supports_tools(self):
        """测试: supports_tools=True 时包含 tools"""
        info = ModelInfo(
            id="tool",
            name="Tool",
            provider="test",
            supports_tools=True,
        )
        assert "tools" in info.features

    def test_features_reasoning_when_supports_reasoning(self):
        """测试: supports_reasoning=True 时包含 reasoning"""
        info = ModelInfo(
            id="reasoner",
            name="Reasoner",
            provider="test",
            supports_reasoning=True,
        )
        assert "reasoning" in info.features

    def test_features_json_mode_when_supports_json_mode(self):
        """测试: supports_json_mode=True 时包含 json_mode"""
        info = ModelInfo(
            id="json",
            name="JSON",
            provider="test",
            supports_json_mode=True,
        )
        assert "json_mode" in info.features

    def test_features_combined(self):
        """测试: 多种能力组合"""
        info = ModelInfo(
            id="full",
            name="Full",
            provider="test",
            supports_vision=True,
            supports_tools=True,
            supports_json_mode=True,
        )
        assert info.features == frozenset({"vision", "tools", "json_mode"})
