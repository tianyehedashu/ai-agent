"""invocation_overrides 应用层单测。"""

import pytest

from domains.gateway.application.ports import InvocationOverrides
from domains.gateway.application.proxy.invocation_overrides import (
    merge_invocation_overrides_into_body,
)
from domains.gateway.domain.catalog.model_capability import ModelCapabilitySnapshot
from domains.gateway.domain.errors import InvocationPolicyViolationError
from domains.gateway.domain.proxy.thinking_param import (
    THINKING_PARAM_DASHSCOPE,
    THINKING_PARAM_DEEPSEEK_V4,
    THINKING_PARAM_NONE,
)


def test_merge_temperature_override() -> None:
    body: dict = {"temperature": 0.7}
    merge_invocation_overrides_into_body(
        body,
        InvocationOverrides(temperature=0.3),
        capabilities=None,
    )
    assert body["temperature"] == 0.3


def test_merge_thinking_dashscope_extra_body() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DASHSCOPE)
    body: dict = {"stream": False}
    merge_invocation_overrides_into_body(
        body,
        InvocationOverrides(thinking_enabled=True),
        capabilities=snap,
    )
    assert body["stream"] is True
    assert body["enable_thinking"] is True
    assert body["extra_body"] == {"enable_thinking": True}


def test_merge_thinking_enabled_without_capabilities_raises() -> None:
    body: dict = {}
    with pytest.raises(InvocationPolicyViolationError):
        merge_invocation_overrides_into_body(
            body,
            InvocationOverrides(thinking_enabled=True),
            capabilities=None,
        )


def test_merge_thinking_disabled_on_unsupported_model_raises() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_NONE)
    with pytest.raises(InvocationPolicyViolationError):
        merge_invocation_overrides_into_body(
            {},
            InvocationOverrides(thinking_enabled=True),
            capabilities=snap,
        )


def test_merge_thinking_deepseek_v4_extra_body() -> None:
    snap = ModelCapabilitySnapshot(thinking_param=THINKING_PARAM_DEEPSEEK_V4)
    body: dict = {}
    merge_invocation_overrides_into_body(
        body,
        InvocationOverrides(thinking_enabled=True),
        capabilities=snap,
    )
    assert body["extra_body"] == {"thinking": {"type": "enabled"}}
