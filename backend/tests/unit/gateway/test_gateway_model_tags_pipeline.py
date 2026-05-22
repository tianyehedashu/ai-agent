"""GatewayModel.tags 写侧 pipeline 单测。"""

from domains.gateway.application.catalog.gateway_model_tags_pipeline import build_gateway_model_tags
from domains.gateway.domain.thinking_param import THINKING_PARAM_ANTHROPIC, THINKING_PARAM_NONE


class _FakeHint:
    def __init__(self, value: bool | None) -> None:
        self._value = value

    def supports_reasoning(self, *, provider: str, real_model: str) -> bool | None:
        _ = provider, real_model
        return self._value


def test_explicit_thinking_param_not_overwritten_by_pipeline() -> None:
    tags = build_gateway_model_tags(
        {"thinking_param": THINKING_PARAM_ANTHROPIC},
        provider="anthropic",
        real_model="claude-3-5-sonnet",
        hint_port=_FakeHint(True),
    )
    assert tags["thinking_param"] == THINKING_PARAM_ANTHROPIC


def test_hint_enables_supports_reasoning_in_pipeline() -> None:
    tags = build_gateway_model_tags(
        {},
        provider="openai",
        real_model="o3-mini",
        hint_port=_FakeHint(True),
    )
    assert tags.get("supports_reasoning") is True
    assert tags.get("thinking_param") != THINKING_PARAM_NONE
