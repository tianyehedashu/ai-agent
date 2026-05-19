"""pricing_proxy_metadata：下游价注入 LiteLLM kwargs。"""

from domains.gateway.application.pricing.pricing_proxy_metadata import (
    apply_downstream_custom_pricing_kwargs,
    downstream_custom_from_metadata,
)


def test_downstream_custom_from_metadata_requires_core_fields() -> None:
    assert downstream_custom_from_metadata({}) is None
    assert (
        downstream_custom_from_metadata(
            {"gateway_pricing_downstream": {"input_cost_per_token": 1e-6}}
        )
        is None
    )


def test_apply_downstream_custom_pricing_kwargs_merges_top_level_and_model_info() -> None:
    kwargs: dict = {
        "metadata": {
            "gateway_pricing_downstream": {
                "input_cost_per_token": 2e-6,
                "output_cost_per_token": 4e-6,
                "cache_read_input_token_cost": 1e-7,
            }
        }
    }
    apply_downstream_custom_pricing_kwargs(kwargs)
    assert kwargs["input_cost_per_token"] == 2e-6
    assert kwargs["output_cost_per_token"] == 4e-6
    assert kwargs["cache_read_input_token_cost"] == 1e-7
    model_info = kwargs["metadata"]["model_info"]
    assert model_info["input_cost_per_token"] == 2e-6
