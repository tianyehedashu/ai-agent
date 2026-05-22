"""LiteLLM capability hint 单测。"""

from domains.gateway.application.catalog.gateway_model_tags_pipeline import build_gateway_model_tags
from domains.gateway.application.catalog.litellm_capability_hint import merge_litellm_reasoning_hint
from domains.gateway.domain.thinking_param import THINKING_PARAM_ANTHROPIC


class _FakeHint:
    def __init__(self, value: bool | None) -> None:
        self._value = value

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        _ = provider, real_model
        return self._value


def test_explicit_thinking_param_not_overwritten() -> None:
    tags = {"thinking_param": THINKING_PARAM_ANTHROPIC}
    out = merge_litellm_reasoning_hint(
        tags,
        provider="anthropic",
        real_model="claude-3",
        hint_port=_FakeHint(True),
    )
    assert out["thinking_param"] == THINKING_PARAM_ANTHROPIC


def test_hint_raises_supports_reasoning() -> None:
    out = merge_litellm_reasoning_hint(
        {},
        provider="openai",
        real_model="o3-mini",
        hint_port=_FakeHint(True),
    )
    assert out.get("supports_reasoning") is True


def test_build_gateway_model_tags_applies_enrich_after_hint() -> None:
    tags = build_gateway_model_tags(
        {},
        provider="openai",
        real_model="o3-mini",
        hint_port=_FakeHint(True),
    )
    assert tags.get("supports_reasoning") is True
    assert "thinking_param" in tags
