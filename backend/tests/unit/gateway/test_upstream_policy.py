"""upstream_policy 领域策略单测。"""

from domains.gateway.domain.upstream_policy import (
    UpstreamCapabilityFlags,
    adapt_kwargs_by_capability,
    clamp_max_tokens,
    is_deepseek_reasoner,
    preprocess_messages_for_reasoner,
)


def test_deepseek_reasoner_message_padding() -> None:
    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x"}}],
        }
    ]
    out = preprocess_messages_for_reasoner("deepseek-reasoner", "deepseek-reasoner", messages)
    assert out[0].get("reasoning_content") == ""


def test_clamp_max_tokens() -> None:
    out = clamp_max_tokens({"max_tokens": 99999}, 8192)
    assert out["max_tokens"] == 8192


def test_reasoning_model_strips_response_format() -> None:
    flags = UpstreamCapabilityFlags(supports_reasoning=True)
    out = adapt_kwargs_by_capability(
        {"response_format": {"type": "json_object"}, "temperature": 0.2},
        flags,
    )
    assert "response_format" not in out
    assert out["temperature"] == 1.0


def test_is_deepseek_reasoner() -> None:
    assert is_deepseek_reasoner("x", "deepseek-reasoner")
