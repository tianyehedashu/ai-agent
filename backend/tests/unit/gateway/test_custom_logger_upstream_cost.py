"""custom_logger：注入下游价后仍按 metadata 上游价记 cost_usd。"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from domains.gateway.infrastructure.callbacks.custom_logger import _calc_cost


def test_calc_cost_prefers_upstream_metadata_over_hidden_downstream() -> None:
    response = MagicMock()
    response._hidden_params = {"response_cost": 0.99}
    kwargs = {
        "model": "virtual-model",
        "metadata": {
            "gateway_pricing_upstream": {
                "input_cost_per_token": 1e-6,
                "output_cost_per_token": 2e-6,
            }
        },
    }
    with patch(
        "domains.gateway.application.upstream.upstream_cost_resolver._completion_cost_upstream",
        return_value=Decimal("0.003"),
    ) as mock_completion_cost:
        cost, source = _calc_cost(kwargs, response)

    assert cost == Decimal("0.003")
    assert source == "upstream_metadata"
    mock_completion_cost.assert_called_once()
