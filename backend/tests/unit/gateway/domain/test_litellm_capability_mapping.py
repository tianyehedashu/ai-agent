"""litellm_capability_mapping 单元测试。"""

from __future__ import annotations

from domains.gateway.domain.litellm_capability_mapping import (
    apply_litellm_hints_to_tags,
    hints_from_model_info,
    hints_without_reasoning,
    strip_litellm_capability_tags,
    tag_hints_from_litellm,
)


def test_hints_from_model_info_extracts_fields() -> None:
    hints = hints_from_model_info(
        {
            "supports_vision": True,
            "supports_reasoning": True,
            "supports_function_calling": True,
            "supports_response_schema": False,
            "mode": "chat",
        }
    )
    assert hints["supports_vision"] is True
    assert hints["supports_reasoning"] is True
    assert hints["mode"] == "chat"


def test_tag_hints_image_generation_mode() -> None:
    mapped = tag_hints_from_litellm({"mode": "image_generation"})
    assert mapped == {"supports_image_gen": True}


def test_fill_missing_only_sets_true_when_key_absent() -> None:
    base = {"supports_vision": False}
    hints = {"supports_vision": True, "supports_function_calling": True}
    out = apply_litellm_hints_to_tags(base, hints, mode="fill_missing")
    assert out["supports_vision"] is False
    assert out["supports_tools"] is True


def test_resync_overwrites_with_false() -> None:
    base = {"supports_vision": True}
    hints = {"supports_vision": False}
    out = apply_litellm_hints_to_tags(base, hints, mode="resync")
    assert out["supports_vision"] is False


def test_strip_litellm_capability_tags() -> None:
    base = {"supports_vision": True, "display_name": "x", "managed_by": "config"}
    out = strip_litellm_capability_tags(base)
    assert "supports_vision" not in out
    assert out["display_name"] == "x"


def test_hints_without_reasoning_omits_reasoning_only() -> None:
    hints = {
        "supports_vision": True,
        "supports_reasoning": True,
        "supports_function_calling": True,
    }
    out = hints_without_reasoning(hints)
    assert out.get("supports_vision") is True
    assert "supports_reasoning" not in out
    assert out.get("supports_function_calling") is True
