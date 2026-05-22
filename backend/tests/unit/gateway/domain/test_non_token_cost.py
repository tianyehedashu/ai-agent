"""non_token_cost 领域策略单元测试。"""

from decimal import Decimal

from domains.gateway.domain.policies.non_token_cost import (
    capability_default_billing_mode,
    estimate_non_token_cost_from_extra,
    merge_non_token_extra_from_litellm,
)
from domains.gateway.domain.types import GatewayCapability


def test_capability_default_billing_mode() -> None:
    assert capability_default_billing_mode(GatewayCapability.CHAT.value) == "token"
    assert capability_default_billing_mode(GatewayCapability.AUDIO_SPEECH.value) == "per_request"
    assert capability_default_billing_mode(GatewayCapability.IMAGE.value) == "hybrid"
    assert capability_default_billing_mode(GatewayCapability.EMBEDDING.value) == "token"


def test_merge_non_token_extra_from_litellm() -> None:
    entry = {
        "input_cost_per_token": 1e-6,
        "input_cost_per_image": 0.04,
        "output_cost_per_second": 0.0001,
        "ignored_key": 99,
    }
    extra = merge_non_token_extra_from_litellm(entry)
    assert extra == {"input_cost_per_image": 0.04, "output_cost_per_second": 0.0001}


def test_estimate_non_token_cost_from_extra_image() -> None:
    response = {"data": [{"url": "https://example.com/a.png"}, {"url": "https://example.com/b.png"}]}
    cost = estimate_non_token_cost_from_extra(
        {"input_cost_per_image": 0.02},
        response,
    )
    assert cost == Decimal("0.04")


def test_estimate_non_token_cost_from_extra_returns_none_when_unmeasurable() -> None:
    cost = estimate_non_token_cost_from_extra(
        {"input_cost_per_image": 0.02},
        None,
    )
    assert cost is None
