"""多能力计价：settlement + resolver 矩阵。"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from domains.gateway.application.pricing.pricing_settlement import settle_request_log_amounts
from domains.gateway.application.upstream.upstream_cost_resolver import (
    resolve_upstream_cost_usd,
)


def test_embedding_style_usage_settlement() -> None:
    cost, revenue, extra = settle_request_log_amounts(
        metadata={
            "gateway_pricing_downstream": {
                "input_cost_per_token": "0.000001",
                "output_cost_per_token": "0.000002",
            }
        },
        litellm_cost_usd=Decimal("0.0005"),
        input_tokens=400,
        output_tokens=0,
        cached_tokens=0,
    )
    assert cost == Decimal("0.0005")
    assert revenue == Decimal("0.0004")
    assert extra.get("metering_mode") == "payg"


def test_image_upstream_metadata_cost() -> None:
    response = MagicMock()
    response.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    metadata = {
        "gateway_pricing_upstream": {
            "input_cost_per_token": 0.04,
            "output_cost_per_token": 0.0,
        },
        "gateway_pricing_downstream": {
            "input_cost_per_token": 0.08,
            "output_cost_per_token": 0.0,
        },
        "gateway_upstream_model": "openai/dall-e-3",
    }
    with patch(
        "domains.gateway.application.upstream.upstream_cost_resolver._completion_cost_upstream",
        return_value=Decimal("0.04"),
    ):
        amount, source = resolve_upstream_cost_usd(
            response=response,
            model="team/image-model",
            metadata=metadata,
        )
    assert amount == Decimal("0.04")
    assert source == "upstream_metadata"


def test_speech_per_request_upstream_cost() -> None:
    metadata = {
        "gateway_pricing_upstream": {
            "per_request_usd": 0.018,
        },
    }
    amount, source = resolve_upstream_cost_usd(
        response=None,
        model="tts-1",
        metadata=metadata,
    )
    assert amount == Decimal("0.018")
    assert source == "per_request"


def test_provider_package_shadow_cost() -> None:
    cost, revenue, extra = settle_request_log_amounts(
        metadata={"gateway_billing_package": "provider"},
        litellm_cost_usd=Decimal("0.02"),
        input_tokens=10,
        output_tokens=10,
        cached_tokens=0,
    )
    assert cost == Decimal("0")
    assert revenue == Decimal("0")
    assert extra.get("shadow_upstream_cost_usd") == 0.02
