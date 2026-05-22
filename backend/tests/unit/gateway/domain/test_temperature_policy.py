"""temperature_policy 推断单测。"""

from domains.gateway.domain.temperature_policy import (
    TEMPERATURE_POLICY_CLIENT,
    TEMPERATURE_POLICY_FIXED_1,
    enrich_temperature_tags,
    infer_temperature_policy,
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


def test_enrich_writes_policy() -> None:
    tags = enrich_temperature_tags({}, thinking_param=THINKING_PARAM_BUILTIN)
    assert tags["temperature_policy"] == TEMPERATURE_POLICY_FIXED_1
