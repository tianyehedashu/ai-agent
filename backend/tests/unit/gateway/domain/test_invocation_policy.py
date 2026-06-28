"""invocation_policy 领域策略单测。"""

import pytest

from domains.gateway.domain.catalog.model_capability import ModelCapabilitySnapshot
from domains.gateway.domain.errors import InvocationPolicyViolationError
from domains.gateway.domain.proxy.invocation_policy import (
    apply_invocation_kwargs,
    client_thinking_request_fields,
    validate_client_thinking_toggle,
    validate_invocation_kwargs,
)
from domains.gateway.domain.proxy.temperature_policy import (
    TEMPERATURE_POLICY_CLIENT,
    TEMPERATURE_POLICY_FIXED_1,
)
from domains.gateway.domain.proxy.thinking_param import (
    THINKING_PARAM_ANTHROPIC,
    THINKING_PARAM_BUILTIN,
    THINKING_PARAM_DASHSCOPE,
    THINKING_PARAM_DEEPSEEK_V4,
    THINKING_PARAM_NONE,
)


def test_none_strips_thinking_fields() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_NONE)
    out = apply_invocation_kwargs(
        snap,
        {
            "enable_thinking": True,
            "thinking": {"type": "enabled", "budget_tokens": 1024},
            "extra_body": {"thinking": {"type": "enabled"}},
            "temperature": 0.5,
        },
        validate=False,
    )
    assert "enable_thinking" not in out
    assert "thinking" not in out
    assert "extra_body" not in out or "thinking" not in out.get("extra_body", {})
    assert out["temperature"] == 0.5


def test_none_strips_thinking_with_validate() -> None:
    """默认 validate=True：不支持思考时剥离而非 400（Claude Code Extended Thinking 等）。"""
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_NONE)
    body = {
        "enable_thinking": True,
        "thinking": {"type": "enabled", "budget_tokens": 1024},
        "extra_body": {"thinking": {"type": "enabled"}},
        "temperature": 0.5,
    }
    validate_invocation_kwargs(snap, body)
    out = apply_invocation_kwargs(snap, body)
    assert "enable_thinking" not in out
    assert "thinking" not in out
    assert "extra_body" not in out or "thinking" not in out.get("extra_body", {})
    assert out["temperature"] == 0.5


def test_dashscope_requires_stream_when_thinking_on() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DASHSCOPE)
    with pytest.raises(InvocationPolicyViolationError):
        validate_invocation_kwargs(
            snap,
            {"enable_thinking": True, "stream": False},
        )


def test_dashscope_allows_stream_with_thinking() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DASHSCOPE)
    validate_invocation_kwargs(
        snap,
        {"enable_thinking": True, "stream": True},
    )


def test_fixed_1_temperature() -> None:
    snap = ModelCapabilitySnapshot(
        thinking_param=THINKING_PARAM_BUILTIN,
        temperature_policy=TEMPERATURE_POLICY_FIXED_1,
    )
    out = apply_invocation_kwargs(snap, {"temperature": 0.2})
    assert out["temperature"] == 1.0


def test_client_temperature_default_and_clamp() -> None:
    snap = ModelCapabilitySnapshot(
        temperature_policy=TEMPERATURE_POLICY_CLIENT,
        temperature_default=0.7,
    )
    out = apply_invocation_kwargs(snap, {})
    assert out["temperature"] == 0.7
    out2 = apply_invocation_kwargs(snap, {"temperature": 5.0})
    assert out2["temperature"] == 2.0


def test_anthropic_extended_strips_enable_thinking() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_ANTHROPIC)
    out = apply_invocation_kwargs(
        snap,
        {
            "enable_thinking": True,
            "thinking": {"type": "enabled", "budget_tokens": 8000},
        },
        validate=False,
    )
    assert "enable_thinking" not in out
    assert out["thinking"]["type"] == "enabled"


def test_client_thinking_fields_dashscope_both_levels() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DASHSCOPE)
    fields = client_thinking_request_fields(snap, enabled=True)
    assert fields["stream"] is True
    assert fields["enable_thinking"] is True
    assert fields["extra_body"] == {"enable_thinking": True}


def test_validate_thinking_toggle_requires_snapshot() -> None:
    with pytest.raises(InvocationPolicyViolationError):
        validate_client_thinking_toggle(None, enabled=True)


def test_validate_thinking_toggle_rejects_none_param() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_NONE)
    with pytest.raises(InvocationPolicyViolationError):
        validate_client_thinking_toggle(snap, enabled=True)


def test_deepseek_v4_preserves_extra_body_thinking() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DEEPSEEK_V4)
    out = apply_invocation_kwargs(
        snap,
        {
            "enable_thinking": True,
            "thinking": {"type": "enabled", "budget_tokens": 8000},
            "extra_body": {"thinking": {"type": "enabled"}},
        },
        validate=False,
    )
    assert "enable_thinking" not in out
    assert "thinking" not in out
    assert out["extra_body"] == {"thinking": {"type": "enabled"}}


def test_deepseek_v4_translates_claude_code_top_level_thinking() -> None:
    """Claude Code /v1/messages 仅传顶层 thinking 时须落到 extra_body.thinking。"""
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DEEPSEEK_V4)
    out = apply_invocation_kwargs(
        snap,
        {
            "model": "deepseek-v4-pro-260425",
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": "hi"}],
            "thinking": {"type": "enabled", "budget_tokens": 1024},
        },
        validate=False,
    )
    assert "thinking" not in out
    assert out["extra_body"] == {"thinking": {"type": "enabled"}}


def test_deepseek_v4_strips_top_level_thinking_when_not_requested() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DEEPSEEK_V4)
    out = apply_invocation_kwargs(
        snap,
        {"messages": [{"role": "user", "content": "hi"}]},
        validate=False,
    )
    assert "thinking" not in out
    assert "extra_body" not in out


def test_client_thinking_fields_deepseek_v4() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DEEPSEEK_V4)
    fields = client_thinking_request_fields(snap, enabled=True)
    assert fields == {"extra_body": {"thinking": {"type": "enabled"}}}
    disabled = client_thinking_request_fields(snap, enabled=False)
    assert disabled == {"extra_body": {"thinking": {"type": "disabled"}}}


def test_apply_invocation_kwargs_returns_original_when_no_changes_needed() -> None:
    """当 capability、thinking、temperature 均无需改写时，应返回原 kwargs 引用。"""
    snap = ModelCapabilitySnapshot(
        thinking_param=THINKING_PARAM_NONE,
        temperature_policy=TEMPERATURE_POLICY_CLIENT,
        temperature_default=0.7,
        supports_tools=True,
        supports_reasoning=False,
        supports_json_mode=True,
    )
    kwargs = {"model": "gpt-4", "temperature": 0.7, "messages": []}
    out = apply_invocation_kwargs(snap, kwargs, validate=False)
    assert out is kwargs


def test_apply_invocation_kwargs_returns_new_object_when_changes_needed() -> None:
    """需要改写时返回新对象，且不污染原 kwargs。"""
    snap = ModelCapabilitySnapshot(
        thinking_param=THINKING_PARAM_NONE,
        temperature_policy=TEMPERATURE_POLICY_FIXED_1,
        supports_tools=True,
        supports_reasoning=False,
        supports_json_mode=True,
    )
    kwargs = {"model": "gpt-4", "temperature": 0.5, "enable_thinking": True}
    out = apply_invocation_kwargs(snap, kwargs, validate=False)
    assert out is not kwargs
    assert "enable_thinking" in kwargs  # 原对象未被污染
    assert "enable_thinking" not in out
    assert out["temperature"] == 1.0
    assert kwargs["temperature"] == 0.5
