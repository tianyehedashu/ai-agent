"""
Product Info Constants 单元测试 - CapabilityConfig / CAPABILITIES
"""

import pytest

from domains.agent.domain.product_info.constants import (
    CAPABILITIES,
    CAPABILITIES_REQUIRING_VISION,
    CAPABILITY_DEPENDENCIES,
    CAPABILITY_IDS,
    CAPABILITY_ORDER,
    CapabilityConfig,
)


@pytest.mark.unit
class TestCapabilityConfig:
    """CapabilityConfig 与 CAPABILITIES 结构测试"""

    def test_image_analysis_requires_vision(self):
        """测试: image_analysis 需要 vision 特性"""
        cfg = CAPABILITIES.get("image_analysis")
        assert cfg is not None
        assert "vision" in cfg.required_features

    def test_text_capabilities_no_vision_required(self):
        """测试: 纯文本能力不要求 vision"""
        text_caps = ["product_link_analysis", "competitor_link_analysis", "video_script", "image_gen_prompts"]
        for cap_id in text_caps:
            cfg = CAPABILITIES.get(cap_id)
            assert cfg is not None
            assert "vision" not in cfg.required_features or cfg.required_features == frozenset()

    def test_capabilities_requiring_vision_matches(self):
        """测试: CAPABILITIES_REQUIRING_VISION 与 CapabilityConfig 一致"""
        expected = {cid for cid, cfg in CAPABILITIES.items() if "vision" in cfg.required_features}
        assert expected == CAPABILITIES_REQUIRING_VISION

    def test_capability_order_derived_from_config(self):
        """测试: CAPABILITY_ORDER 从 CAPABILITIES 派生且有序"""
        sorted_ids = [cid for _, cid in sorted(CAPABILITY_ORDER, key=lambda x: x[0])]
        assert sorted_ids == [c.id for c in sorted(CAPABILITIES.values(), key=lambda x: x.sort_order)]

    def test_capability_dependencies_derived(self):
        """测试: CAPABILITY_DEPENDENCIES 与 CapabilityConfig 一致"""
        for cap_id, cfg in CAPABILITIES.items():
            assert list(cfg.dependencies) == CAPABILITY_DEPENDENCIES.get(cap_id, [])

    def test_all_capability_ids_have_config(self):
        """测试: 每个 CAPABILITY_IDS 都有对应配置"""
        for cap_id in CAPABILITY_IDS:
            assert cap_id in CAPABILITIES
            assert isinstance(CAPABILITIES[cap_id], CapabilityConfig)

    def test_capability_config_has_required_fields(self):
        """测试: 每个 CapabilityConfig 包含必要字段"""
        required_attrs = ["id", "name", "sort_order", "output_key", "dependencies", "input_fields", "required_features"]
        for cfg in CAPABILITIES.values():
            for attr in required_attrs:
                assert hasattr(cfg, attr), f"CapabilityConfig {cfg.id} 缺少 {attr}"
