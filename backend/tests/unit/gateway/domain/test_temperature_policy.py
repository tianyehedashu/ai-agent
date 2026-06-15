"""temperature_policy 推断单测。"""

from domains.gateway.domain.model_capability import tags_to_capability_snapshot
from domains.gateway.domain.policies.invocation_policy import apply_invocation_kwargs
from domains.gateway.domain.temperature_policy import (
    TEMPERATURE_POLICY_CLIENT,
    TEMPERATURE_POLICY_FIXED_1,
    enrich_temperature_tags,
    infer_temperature_policy,
    requires_fixed_temperature_1,
)
from domains.gateway.domain.thinking_param import THINKING_PARAM_BUILTIN, THINKING_PARAM_NONE


def test_infer_fixed_1_for_reasoning() -> None:
    assert (
        infer_temperature_policy(
            thinking_param=THINKING_PARAM_BUILTIN,
            supports_reasoning=True,
        )
        == TEMPERATURE_POLICY_FIXED_1
    )


def test_infer_client_for_chat() -> None:
    assert (
        infer_temperature_policy(
            thinking_param=THINKING_PARAM_NONE,
            supports_reasoning=False,
        )
        == TEMPERATURE_POLICY_CLIENT
    )


def test_kimi_for_coding_requires_fixed_1() -> None:
    assert requires_fixed_temperature_1(real_model="kimi-for-coding")
    assert requires_fixed_temperature_1(real_model="kimi-for-coding-chat")
    assert requires_fixed_temperature_1(real_model="moonshot/kimi-for-coding")
    assert not requires_fixed_temperature_1(real_model="moonshot-v1-8k")
    assert not requires_fixed_temperature_1(real_model="my-for-coding-test")


def test_kimi_for_coding_fixed_1_even_when_thinking_locked() -> None:
    assert (
        infer_temperature_policy(
            thinking_param=THINKING_PARAM_NONE,
            supports_reasoning=False,
            real_model="kimi-for-coding",
        )
        == TEMPERATURE_POLICY_FIXED_1
    )


def test_kimi_for_coding_overrides_explicit_client_policy() -> None:
    assert (
        infer_temperature_policy(
            thinking_param=THINKING_PARAM_NONE,
            supports_reasoning=False,
            explicit=TEMPERATURE_POLICY_CLIENT,
            real_model="kimi-for-coding",
        )
        == TEMPERATURE_POLICY_FIXED_1
    )
    snap = tags_to_capability_snapshot(
        {"temperature_policy": "client"},
        provider="moonshot",
        real_model="kimi-for-coding",
    )
    assert snap.temperature_policy == TEMPERATURE_POLICY_FIXED_1


def test_kimi_for_coding_locked_tags_apply_temperature_1() -> None:
    snap = tags_to_capability_snapshot(
        {"thinking_param": "none", "thinking_param_locked": True},
        provider="moonshot",
        real_model="kimi-for-coding",
    )
    assert snap.temperature_policy == TEMPERATURE_POLICY_FIXED_1
    out = apply_invocation_kwargs(snap, {"temperature": 0.2})
    assert out["temperature"] == 1.0


def test_enrich_writes_policy() -> None:
    tags = enrich_temperature_tags({}, thinking_param=THINKING_PARAM_BUILTIN)
    assert tags["temperature_policy"] == TEMPERATURE_POLICY_FIXED_1
