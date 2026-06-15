"""temperature_policy 推断单测。"""

from domains.gateway.domain.model_capability import tags_to_capability_snapshot
from domains.gateway.domain.policies.invocation_policy import apply_invocation_kwargs
from domains.gateway.domain.temperature_policy import (
    TEMPERATURE_POLICY_CLIENT,
    TEMPERATURE_POLICY_FIXED_1,
    UPSTREAM_PROFILE_ID_TAG,
    enrich_temperature_tags,
    infer_temperature_policy,
    temperature_policy_from_upstream_profile,
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


def test_moonshot_coding_plan_profile_requires_fixed_1() -> None:
    assert (
        temperature_policy_from_upstream_profile(
            credential_profile_id="moonshot.coding_plan",
            provider="moonshot",
        )
        == TEMPERATURE_POLICY_FIXED_1
    )
    assert (
        temperature_policy_from_upstream_profile(
            credential_profile_id=None,
            provider="moonshot",
        )
        is None
    )


def test_coding_plan_fixed_1_even_when_thinking_locked() -> None:
    assert (
        infer_temperature_policy(
            thinking_param=THINKING_PARAM_NONE,
            supports_reasoning=False,
            credential_profile_id="moonshot.coding_plan",
            provider="moonshot",
        )
        == TEMPERATURE_POLICY_FIXED_1
    )


def test_coding_plan_overrides_explicit_client_policy() -> None:
    assert (
        infer_temperature_policy(
            thinking_param=THINKING_PARAM_NONE,
            supports_reasoning=False,
            explicit=TEMPERATURE_POLICY_CLIENT,
            credential_profile_id="moonshot.coding_plan",
            provider="moonshot",
        )
        == TEMPERATURE_POLICY_FIXED_1
    )
    snap = tags_to_capability_snapshot(
        {
            "temperature_policy": "client",
            UPSTREAM_PROFILE_ID_TAG: "moonshot.coding_plan",
        },
        provider="moonshot",
        real_model="my-custom-code-model",
    )
    assert snap.temperature_policy == TEMPERATURE_POLICY_FIXED_1


def test_coding_plan_locked_tags_apply_temperature_1() -> None:
    snap = tags_to_capability_snapshot(
        {
            "thinking_param": "none",
            "thinking_param_locked": True,
            UPSTREAM_PROFILE_ID_TAG: "moonshot.coding_plan",
        },
        provider="moonshot",
        real_model="my-custom-code-model",
    )
    assert snap.temperature_policy == TEMPERATURE_POLICY_FIXED_1
    out = apply_invocation_kwargs(snap, {"temperature": 0.2})
    assert out["temperature"] == 1.0


def test_enrich_writes_policy() -> None:
    tags = enrich_temperature_tags({}, thinking_param=THINKING_PARAM_BUILTIN)
    assert tags["temperature_policy"] == TEMPERATURE_POLICY_FIXED_1
