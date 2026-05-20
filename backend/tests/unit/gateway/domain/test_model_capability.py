"""``domains.gateway.domain.model_capability`` 单元测试。"""

from domains.gateway.domain.model_capability import (
    ModelCapabilitySnapshot,
    tags_to_capability_snapshot,
)


def test_tags_to_capability_snapshot_defaults() -> None:
    snap = tags_to_capability_snapshot({})
    assert snap.supports_tools is True
    assert snap.supports_image_gen is False
    assert snap.supports_txt2img is False


def test_tags_to_capability_snapshot_image_gen_defaults_txt2img() -> None:
    snap = tags_to_capability_snapshot({"supports_image_gen": True})
    assert snap.supports_txt2img is True
    assert snap.supports_img2img is True


def test_features_property() -> None:
    snap = ModelCapabilitySnapshot(
        supports_vision=True,
        supports_tools=False,
        supports_json_mode=False,
        supports_txt2img=False,
    )
    assert snap.features == frozenset({"vision"})
