"""pipeline_policy 单元测试。"""

import pytest

from domains.agent.domain.listing_studio.pipeline_policy import build_execution_layers


@pytest.mark.unit
class TestBuildExecutionLayers:
    def test_independent_caps_single_layer(self):
        caps = [(1, "image_analysis"), (2, "product_link_analysis")]
        layers = build_execution_layers(caps)
        assert len(layers) == 1
        assert {c for _, c in layers[0]} == {"image_analysis", "product_link_analysis"}

    def test_dependency_creates_two_layers(self):
        caps = [
            (1, "product_link_analysis"),
            (2, "video_script"),
        ]
        layers = build_execution_layers(caps)
        assert len(layers) == 2
        assert layers[0][0][1] == "product_link_analysis"
        assert layers[1][0][1] == "video_script"

    def test_full_pipeline_order(self):
        caps = [
            (1, "image_analysis"),
            (2, "product_link_analysis"),
            (3, "competitor_link_analysis"),
            (4, "video_script"),
            (5, "image_gen_prompts"),
        ]
        layers = build_execution_layers(caps)
        layer_ids = [[c for _, c in layer] for layer in layers]
        assert {"image_analysis", "product_link_analysis", "competitor_link_analysis"} <= set(
            layer_ids[0]
        )
        assert "video_script" in layer_ids[1]
        assert "image_gen_prompts" in layer_ids[2]
