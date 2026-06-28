"""upstream_cost_resolver 单元测试。"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from domains.gateway.application.upstream.upstream_cost_resolver import (
    SOURCE_LITELLM_HIDDEN,
    SOURCE_NON_TOKEN_EXTRA,
    SOURCE_PER_REQUEST,
    SOURCE_UPSTREAM_METADATA,
    SOURCE_ZERO,
    resolve_upstream_cost_usd,
)


def test_prefers_upstream_metadata_over_hidden_downstream() -> None:
    response = MagicMock()
    response._hidden_params = {"response_cost": 0.99}
    metadata = {
        "gateway_pricing_downstream": {
            "input_cost_per_token": 1e-5,
            "output_cost_per_token": 2e-5,
        },
        "gateway_pricing_upstream": {
            "input_cost_per_token": 1e-6,
            "output_cost_per_token": 2e-6,
        },
    }
    with patch(
        "domains.gateway.application.upstream.upstream_cost_resolver._completion_cost_upstream",
        return_value=Decimal("0.003"),
    ):
        cost, source = resolve_upstream_cost_usd(
            response=response,
            model="team/virtual",
            metadata=metadata,
        )
    assert cost == Decimal("0.003")
    assert source == SOURCE_UPSTREAM_METADATA


def test_skips_hidden_when_downstream_pricing_applied() -> None:
    response = MagicMock()
    response._hidden_params = {"response_cost": 0.99}
    metadata = {
        "gateway_pricing_downstream": {
            "input_cost_per_token": 1e-5,
            "output_cost_per_token": 2e-5,
        },
        "gateway_upstream_model": "openai/gpt-4o",
    }
    with patch(
        "domains.gateway.application.upstream.upstream_cost_resolver._completion_cost_upstream",
        return_value=Decimal("0.001"),
    ) as mock_cc:
        cost, source = resolve_upstream_cost_usd(
            response=response,
            model="team/virtual",
            metadata=metadata,
        )
    assert cost == Decimal("0.001")
    assert source != SOURCE_LITELLM_HIDDEN
    mock_cc.assert_called()
    assert mock_cc.call_args.kwargs["model"] == "openai/gpt-4o"


def test_uses_hidden_when_no_downstream() -> None:
    response = MagicMock()
    response._hidden_params = {"response_cost": 0.42}
    cost, source = resolve_upstream_cost_usd(
        response=response,
        model="gpt-4o",
        metadata={},
    )
    assert cost == Decimal("0.42")
    assert source == SOURCE_LITELLM_HIDDEN


def test_zero_when_nothing_matches() -> None:
    response = MagicMock()
    response._hidden_params = {}
    response.usage = None
    with patch(
        "domains.gateway.application.upstream.upstream_cost_resolver._completion_cost_upstream",
        return_value=None,
    ):
        cost, source = resolve_upstream_cost_usd(
            response=response,
            model="unknown",
            metadata={},
        )
    assert cost == Decimal("0")
    assert source == SOURCE_ZERO


def test_per_request_upstream_metadata() -> None:
    metadata = {
        "gateway_pricing_upstream": {
            "per_request_usd": 0.015,
        },
    }
    cost, source = resolve_upstream_cost_usd(
        response=None,
        model="tts-1",
        metadata=metadata,
    )
    assert cost == Decimal("0.015")
    assert source == SOURCE_PER_REQUEST


def test_non_token_extra_image_cost() -> None:
    response = {"data": [{"url": "https://example.com/a.png"}, {"url": "https://b.png"}]}
    metadata = {
        "gateway_pricing_upstream": {
            "input_cost_per_image": 0.02,
        },
    }
    cost, source = resolve_upstream_cost_usd(
        response=response,
        model="dall-e",
        metadata=metadata,
    )
    assert cost == Decimal("0.04")
    assert source == SOURCE_NON_TOKEN_EXTRA


def test_skips_litellm_completion_for_per_request_capability_without_token_rates() -> None:
    response = MagicMock()
    metadata = {
        "gateway_capability": "audio_speech",
        "gateway_upstream_model": "openai/tts-1",
        "gateway_pricing_upstream": {"per_request_usd": 0.015},
    }
    with patch(
        "domains.gateway.application.upstream.upstream_cost_resolver._completion_cost_upstream",
        return_value=Decimal("0.99"),
    ) as mock_cc:
        cost, source = resolve_upstream_cost_usd(
            response=response,
            model="tts-1",
            metadata=metadata,
        )
    assert cost == Decimal("0.015")
    assert source == SOURCE_PER_REQUEST
    mock_cc.assert_not_called()
