"""upstream_policy 领域策略单测。"""

from domains.gateway.domain.model_capability import ModelCapabilitySnapshot
from domains.gateway.domain.policies.invocation_policy import apply_invocation_kwargs
from domains.gateway.domain.temperature_policy import TEMPERATURE_POLICY_FIXED_1
from domains.gateway.domain.upstream_policy import (
    clamp_max_tokens,
    is_deepseek_reasoner,
    is_deepseek_thinking_model,
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
    snap = ModelCapabilitySnapshot(
        supports_reasoning=True,
        temperature_policy=TEMPERATURE_POLICY_FIXED_1,
    )
    out = apply_invocation_kwargs(
        snap,
        {"response_format": {"type": "json_object"}, "temperature": 0.2},
        validate=False,
    )
    assert "response_format" not in out
    assert out["temperature"] == 1.0


def test_is_deepseek_reasoner() -> None:
    assert is_deepseek_reasoner("x", "deepseek-reasoner")


def test_deepseek_v4_message_padding() -> None:
    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x"}}],
        }
    ]
    out = preprocess_messages_for_reasoner(
        "deepseek-v4-pro-260425",
        "deepseek-v4-pro",
        messages,
    )
    assert out[0].get("reasoning_content") == ""


def test_is_deepseek_thinking_model_v4() -> None:
    assert is_deepseek_thinking_model("deepseek-v4-pro-260425", "deepseek-v4-pro")


def test_deepseek_reasoner_content_array_extracts_text() -> None:
    """content 为 content-parts 数组时，reasoning_content 应提取为字符串而非保留 list。"""
    messages = [
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "thoughts"}],
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x"}}],
        }
    ]
    out = preprocess_messages_for_reasoner("deepseek-reasoner", "deepseek-reasoner", messages)
    assert out[0].get("reasoning_content") == "thoughts"
    assert isinstance(out[0].get("reasoning_content"), str)
