"""invocation_policy 领域策略单测。"""

import pytest

from domains.gateway.domain.errors import InvocationPolicyViolationError
from domains.gateway.domain.model_capability import ModelCapabilitySnapshot
from domains.gateway.domain.policies.invocation_policy import (
    apply_invocation_kwargs,
    client_thinking_request_fields,
    validate_client_thinking_toggle,
    validate_invocation_kwargs,
)
from domains.gateway.domain.temperature_policy import (
    TEMPERATURE_POLICY_CLIENT,
    TEMPERATURE_POLICY_FIXED_1,
)
from domains.gateway.domain.thinking_param import (
    THINKING_PARAM_ANTHROPIC,
    THINKING_PARAM_BUILTIN,
    THINKING_PARAM_DASHSCOPE,
    THINKING_PARAM_NONE,
)


def test_none_strips_thinking_fields() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_NONE)
    out = apply_invocation_kwargs(
        snap,
        {
            "enable_thinking": True,
            "thinking": {"type": "enabled", "budget_tokens": 1024},
            "temperature": 0.5,
        },
        validate=False,
    )
    assert "enable_thinking" not in out
    assert "thinking" not in out
    assert out["temperature"] == 0.5


def test_none_strips_thinking_with_validate() -> None:
    """默认 validate=True：不支持思考时剥离而非 400（Claude Code Extended Thinking 等）。"""
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_NONE)
    body = {
        "enable_thinking": True,
        "thinking": {"type": "enabled", "budget_tokens": 1024},
        "temperature": 0.5,
    }
    validate_invocation_kwargs(snap, body)
    out = apply_invocation_kwargs(snap, body)
    assert "enable_thinking" not in out
    assert "thinking" not in out
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
