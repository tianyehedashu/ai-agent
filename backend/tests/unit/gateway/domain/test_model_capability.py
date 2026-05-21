"""``domains.gateway.domain.model_capability`` 单元测试。"""

from domains.gateway.domain.model_capability import (
    ModelCapabilitySnapshot,
    tags_to_capability_snapshot,
)
from domains.gateway.domain.thinking_param import (
    THINKING_PARAM_DASHSCOPE,
    THINKING_PARAM_NONE,
)


def test_tags_to_capability_snapshot_defaults() -> None:
    snap = tags_to_capability_snapshot({})
    assert snap.supports_tools is True
    assert snap.supports_image_gen is False
    assert snap.supports_txt2img is False
    assert snap.thinking_param == THINKING_PARAM_NONE


def test_tags_to_capability_snapshot_image_gen_defaults_txt2img() -> None:
    snap = tags_to_capability_snapshot({"supports_image_gen": True})
    assert snap.supports_txt2img is True
    assert snap.supports_img2img is True


def test_tags_to_capability_snapshot_qwen3_with_provider() -> None:
    snap = tags_to_capability_snapshot(
        {"supports_reasoning_content": True},
        provider="dashscope",
        real_model="qwen3-32b",
    )
    assert snap.thinking_param == THINKING_PARAM_DASHSCOPE
    assert snap.supports_reasoning is True


def test_features_property() -> None:
    snap = ModelCapabilitySnapshot(
        supports_vision=True,
        supports_tools=False,
        supports_json_mode=False,
        supports_txt2img=False,
    )
    assert snap.features == frozenset({"vision"})
