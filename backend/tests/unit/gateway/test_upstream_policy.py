"""upstream_policy 领域策略单测。"""

from domains.gateway.domain.model_capability import ModelCapabilitySnapshot
from domains.gateway.domain.policies.invocation_policy import apply_invocation_kwargs
from domains.gateway.domain.temperature_policy import TEMPERATURE_POLICY_FIXED_1
from domains.gateway.domain.thinking_param import is_moonshot_model
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


def test_is_moonshot_thinking_model_kimi() -> None:
    assert is_moonshot_model("kimi-for-coding-chat")
    assert is_moonshot_model("kimi-for-coding")


def test_is_moonshot_thinking_model_moonshot() -> None:
    assert is_moonshot_model("moonshot-v1-128k")


def test_is_moonshot_thinking_model_negative() -> None:
    assert not is_moonshot_model("gpt-4o")
    assert not is_moonshot_model("")


def test_moonshot_kimi_message_padding_without_supports_reasoning() -> None:
    """Moonshot/Kimi 模型不传 supports_reasoning 时也应回填 reasoning_content。"""
    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "read_file"}}],
        }
    ]
    out = preprocess_messages_for_reasoner(
        "kimi-for-coding-chat",
        "kimi-for-coding",
        messages,
    )
    assert out[0].get("reasoning_content") == ""


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


def test_generic_reasoning_model_message_padding() -> None:
    """supports_reasoning=True 时对任意 thinking 模型（如 Moonshot/Kimi）回填 reasoning_content。"""
    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "read_file"}}],
        }
    ]
    out = preprocess_messages_for_reasoner(
        "kimi-for-coding-chat",
        "kimi-for-coding",
        messages,
        supports_reasoning=True,
    )
    assert out[0].get("reasoning_content") == ""


def test_generic_reasoning_model_content_array_extracts_text() -> None:
    """supports_reasoning=True + content-parts 数组时提取纯文本。"""
    messages = [
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "analysis"}],
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x"}}],
        }
    ]
    out = preprocess_messages_for_reasoner(
        "some-model",
        "some-real-model",
        messages,
        supports_reasoning=True,
    )
    assert out[0].get("reasoning_content") == "analysis"
    assert isinstance(out[0].get("reasoning_content"), str)


def test_non_reasoning_model_skips_padding() -> None:
    """非 thinking 模型且 supports_reasoning=False 时不应添加 reasoning_content。"""
    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x"}}],
        }
    ]
    out = preprocess_messages_for_reasoner(
        "gpt-4o",
        "gpt-4o",
        messages,
        supports_reasoning=False,
    )
    assert "reasoning_content" not in out[0]


def test_existing_reasoning_content_preserved() -> None:
    """已有 reasoning_content 的消息不应被覆盖。"""
    messages = [
        {
            "role": "assistant",
            "content": "response",
            "reasoning_content": "original thought",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x"}}],
        }
    ]
    out = preprocess_messages_for_reasoner(
        "kimi-for-coding-chat",
        "kimi-for-coding",
        messages,
        supports_reasoning=True,
    )
    assert out[0].get("reasoning_content") == "original thought"


def test_deepseek_backward_compat_without_supports_reasoning() -> None:
    """向后兼容：DeepSeek 模型不传 supports_reasoning 时仍正常工作。"""
    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x"}}],
        }
    ]
    out = preprocess_messages_for_reasoner("deepseek-reasoner", "deepseek-reasoner", messages)
    assert out[0].get("reasoning_content") == ""


def test_preprocess_messages_for_reasoner_returns_original_when_no_change() -> None:
    """无需回填 reasoning_content 时返回原列表引用。"""
    messages = [{"role": "user", "content": "hello"}]
    out = preprocess_messages_for_reasoner(
        "gpt-4o",
        "gpt-4o",
        messages,
        supports_reasoning=False,
    )
    assert out is messages


def test_clamp_max_tokens_returns_original_when_within_range() -> None:
    kwargs = {"max_tokens": 100, "messages": []}
    out = clamp_max_tokens(kwargs, 8192)
    assert out is kwargs


def test_clamp_max_tokens_returns_new_object_when_out_of_range() -> None:
    kwargs = {"max_tokens": 99999, "messages": []}
    out = clamp_max_tokens(kwargs, 8192)
    assert out is not kwargs
    assert out["max_tokens"] == 8192
    assert kwargs["max_tokens"] == 99999
