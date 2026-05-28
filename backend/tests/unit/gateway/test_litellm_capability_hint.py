"""LiteLLM capability hint 单测。"""

from domains.gateway.application.catalog.gateway_model_tags_pipeline import build_gateway_model_tags
from domains.gateway.application.catalog.litellm_capability_hint import (
    merge_litellm_capability_hints,
    merge_litellm_reasoning_hint,
)
from domains.gateway.application.upstream_model_types_for_catalog import (
    infer_upstream_model_types_for_catalog,
)
from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints
from domains.gateway.domain.thinking_param import THINKING_PARAM_ANTHROPIC


class _FakeHint:
    def __init__(self, hints: LitellmModelInfoHints | None) -> None:
        self._hints = hints

    def get_model_hints(self, *, provider: str, real_model: str) -> LitellmModelInfoHints | None:
        _ = provider, real_model
        return self._hints

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        hints = self.get_model_hints(provider=provider, real_model=real_model)
        if hints is None:
            return None
        value = hints.get("supports_reasoning")
        return value if isinstance(value, bool) else None


def test_explicit_thinking_param_not_overwritten() -> None:
    tags = {"thinking_param": THINKING_PARAM_ANTHROPIC}
    out = merge_litellm_reasoning_hint(
        tags,
        provider="anthropic",
        real_model="claude-3",
        hint_port=_FakeHint({"supports_reasoning": True, "supports_vision": True}),
    )
    assert out["thinking_param"] == THINKING_PARAM_ANTHROPIC
    assert out.get("supports_reasoning") is not True
    assert out.get("supports_vision") is True


def test_hint_raises_supports_reasoning() -> None:
    out = merge_litellm_reasoning_hint(
        {},
        provider="openai",
        real_model="o3-mini",
        hint_port=_FakeHint({"supports_reasoning": True}),
    )
    assert out.get("supports_reasoning") is True


def test_build_gateway_model_tags_applies_enrich_after_hint() -> None:
    tags = build_gateway_model_tags(
        {},
        provider="openai",
        real_model="o3-mini",
        hint_port=_FakeHint({"supports_reasoning": True}),
    )
    assert tags.get("supports_reasoning") is True
    assert "thinking_param" in tags


def test_merge_capability_hints_sets_vision_fill_missing() -> None:
    out = merge_litellm_capability_hints(
        {},
        provider="volcengine",
        real_model="volcengine/doubao-seed-2-0-lite-260215",
        hint_port=_FakeHint({"supports_vision": True, "supports_reasoning": True}),
        mode="fill_missing",
    )
    assert out.get("supports_vision") is True
    assert out.get("supports_reasoning") is True


def test_resync_overwrites_vision_false() -> None:
    out = merge_litellm_capability_hints(
        {"supports_vision": True},
        provider="openai",
        real_model="gpt-3.5-turbo",
        hint_port=_FakeHint({"supports_vision": False}),
        mode="resync",
    )
    assert out.get("supports_vision") is False


def test_skip_hints_leaves_tags_unchanged() -> None:
    base = {"supports_vision": False}
    out = merge_litellm_capability_hints(
        base,
        provider="volcengine",
        real_model="volcengine/doubao-seed-2-0-lite-260215",
        hint_port=_FakeHint({"supports_vision": True}),
        skip_hints=True,
    )
    assert out.get("supports_vision") is False


def test_infer_upstream_model_types_for_catalog_unions_litellm() -> None:
    types = infer_upstream_model_types_for_catalog(
        "volcengine",
        "doubao-seed-2-0-lite-260215",
        hint_port=_FakeHint({"supports_vision": True}),
    )
    assert "text" in types
    assert "image" in types
