"""Gateway LiteLLM cost 计算回归测试。"""

from decimal import Decimal
from types import SimpleNamespace

import litellm

from domains.gateway.infrastructure.callbacks.custom_logger import _calc_cost, _extract_usage


def test_calc_cost_prefers_litellm_hidden_response_cost() -> None:
    response = SimpleNamespace(_hidden_params={"response_cost": "0.000123"})

    cost = _calc_cost(
        {
            "model": "zai/glm-4-flash",
            "standard_logging_object": {"response_cost": "0.999"},
        },
        response,
    )

    assert cost == Decimal("0.000123")


def test_calc_cost_reads_hidden_params_object() -> None:
    response = SimpleNamespace(
        _hidden_params=SimpleNamespace(response_cost=Decimal("0.000456"))
    )

    assert _calc_cost({"model": "virtual-model"}, response) == Decimal("0.000456")


def test_calc_cost_falls_back_to_standard_logging_object() -> None:
    response = SimpleNamespace(_hidden_params={})

    cost = _calc_cost(
        {"model": "virtual-model", "standard_logging_object": {"response_cost": 0.000789}},
        response,
    )

    assert cost == Decimal("0.000789")


def test_calc_cost_uses_litellm_completion_cost_as_last_resort(monkeypatch) -> None:
    response = SimpleNamespace(_hidden_params={})
    monkeypatch.setattr(litellm, "completion_cost", lambda **_kwargs: 0.000111)

    assert _calc_cost({"model": "known-model"}, response) == Decimal("0.000111")


def test_extract_usage_reads_cached_tokens_from_details_dict() -> None:
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            prompt_tokens_details={"cached_tokens": 3},
        )
    )

    assert _extract_usage(response) == (10, 5, 3)


def test_extract_usage_reads_cached_tokens_from_details_object() -> None:
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            prompt_tokens_details=SimpleNamespace(cached_tokens=4),
        )
    )

    assert _extract_usage(response) == (10, 5, 4)
