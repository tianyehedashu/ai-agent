"""GatewayModel.tags 写侧 pipeline 单测。"""

from domains.gateway.application.catalog.gateway_model_tags_pipeline import build_gateway_model_tags
from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints
from domains.gateway.domain.thinking_param import THINKING_PARAM_ANTHROPIC, THINKING_PARAM_NONE


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


def test_explicit_thinking_param_not_overwritten_by_pipeline() -> None:
    tags = build_gateway_model_tags(
        {"thinking_param": THINKING_PARAM_ANTHROPIC},
        provider="anthropic",
        real_model="claude-3-5-sonnet",
        hint_port=_FakeHint({"supports_reasoning": True}),
    )
    assert tags["thinking_param"] == THINKING_PARAM_ANTHROPIC


def test_hint_enables_supports_reasoning_in_pipeline() -> None:
    tags = build_gateway_model_tags(
        {},
        provider="openai",
        real_model="o3-mini",
        hint_port=_FakeHint({"supports_reasoning": True}),
    )
    assert tags.get("supports_reasoning") is True
    assert tags.get("thinking_param") != THINKING_PARAM_NONE


def test_resync_mode_sets_vision_in_pipeline() -> None:
    tags = build_gateway_model_tags(
        {},
        provider="volcengine",
        real_model="volcengine/doubao-seed-2-0-lite-260215",
        hint_port=_FakeHint({"supports_vision": True}),
        hint_mode="resync",
    )
    assert tags.get("supports_vision") is True


def test_upstream_profile_id_denormalized_into_tags() -> None:
    tags = build_gateway_model_tags(
        {},
        provider="moonshot",
        real_model="my-code-model",
        upstream_profile_id="moonshot.coding_plan",
    )
    assert tags["upstream_profile_id"] == "moonshot.coding_plan"
    assert tags["temperature_policy"] == "fixed_1"
