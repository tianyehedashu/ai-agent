"""统一上游成本（USD）解析：预算、日志、Playground 共用。

``_hidden_params.response_cost`` 在注入下游价后为**售价**，不可直接作为上游成本。
"""

from __future__ import annotations

from contextlib import suppress
from decimal import Decimal
import logging
from typing import Any

from domains.gateway.application.pricing.pricing_settlement import pricing_rate_from_metadata
from domains.gateway.domain.pricing_calculator import TokenUsage, calculate_cost_from_rate

logger = logging.getLogger(__name__)

SOURCE_UPSTREAM_METADATA = "upstream_metadata"
SOURCE_LITELLM_HIDDEN = "litellm_hidden"
SOURCE_LITELLM_SLO = "litellm_slo"
SOURCE_LITELLM_COMPLETION = "litellm_completion"
SOURCE_DOMAIN_FALLBACK = "domain_fallback"
SOURCE_ZERO = "zero"


def _has_downstream_pricing(metadata: dict[str, Any]) -> bool:
    downstream = metadata.get("gateway_pricing_downstream")
    if not isinstance(downstream, dict):
        return False
    return (
        downstream.get("input_cost_per_token") is not None
        and downstream.get("output_cost_per_token") is not None
    )


def _read_hidden_response_cost(response_obj: Any) -> Decimal | None:
    if response_obj is None:
        return None
    hp = getattr(response_obj, "_hidden_params", None)
    if hp is None:
        return None
    raw = hp.get("response_cost") if isinstance(hp, dict) else getattr(hp, "response_cost", None)
    if raw is None:
        return None
    with suppress(Exception):
        return Decimal(str(raw))
    return None


def _extract_usage_from_response(response_obj: Any) -> TokenUsage:
    if response_obj is None:
        return TokenUsage()
    usage = getattr(response_obj, "usage", None)
    if usage is None and isinstance(response_obj, dict):
        usage = response_obj.get("usage")
    if usage is None:
        return TokenUsage()
    if isinstance(usage, dict):
        return TokenUsage(
            input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            cache_read_tokens=int(
                usage.get("cache_read_input_tokens")
                or usage.get("cached_tokens")
                or 0
            ),
            cache_creation_tokens=int(usage.get("cache_creation_input_tokens") or 0),
        )
    return TokenUsage(
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(
            getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0
        ),
        cache_read_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        cache_creation_tokens=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
    )


def _completion_cost_upstream(
    response_obj: Any,
    *,
    model: str | None,
    custom_cost_per_token: dict[str, Any] | None,
) -> Decimal | None:
    try:
        from litellm import completion_cost

        cost = completion_cost(
            completion_response=response_obj,
            model=model,
            custom_cost_per_token=custom_cost_per_token,
        )
        return Decimal(str(cost or 0))
    except Exception as exc:  # pragma: no cover
        logger.debug("completion_cost failed model=%s: %s", model, exc)
        return None


def resolve_upstream_cost_usd(
    *,
    response: Any,
    model: str | None,
    metadata: dict[str, Any],
    standard_logging: dict[str, Any] | None = None,
) -> tuple[Decimal, str]:
    """返回 (上游成本 USD, source_tag)。"""
    downstream_applied = _has_downstream_pricing(metadata)

    upstream_custom = metadata.get("gateway_pricing_upstream")
    if isinstance(upstream_custom, dict):
        inp = upstream_custom.get("input_cost_per_token")
        out = upstream_custom.get("output_cost_per_token")
        if inp is not None and out is not None:
            cost = _completion_cost_upstream(
                response,
                model=model,
                custom_cost_per_token=upstream_custom,
            )
            if cost is not None:
                return cost, SOURCE_UPSTREAM_METADATA

    if not downstream_applied:
        hidden_cost = _read_hidden_response_cost(response)
        if hidden_cost is not None:
            return hidden_cost, SOURCE_LITELLM_HIDDEN

        slo = standard_logging
        if isinstance(slo, dict):
            slo_cost = slo.get("response_cost")
            if slo_cost is not None:
                with suppress(Exception):
                    return Decimal(str(slo_cost)), SOURCE_LITELLM_SLO

    litellm_model = metadata.get("gateway_upstream_model")
    if litellm_model is not None:
        litellm_model = str(litellm_model)
    cost = _completion_cost_upstream(response, model=litellm_model, custom_cost_per_token=None)
    if cost is not None and cost > 0:
        return cost, SOURCE_LITELLM_COMPLETION

    if isinstance(upstream_custom, dict):
        rate = pricing_rate_from_metadata(upstream_custom)
        if rate is not None:
            usage = _extract_usage_from_response(response)
            domain_cost = calculate_cost_from_rate(rate, usage).amount
            if domain_cost > 0:
                return domain_cost, SOURCE_DOMAIN_FALLBACK

    if cost is not None:
        return cost, SOURCE_LITELLM_COMPLETION
    return Decimal("0"), SOURCE_ZERO


__all__ = [
    "SOURCE_DOMAIN_FALLBACK",
    "SOURCE_LITELLM_COMPLETION",
    "SOURCE_LITELLM_HIDDEN",
    "SOURCE_LITELLM_SLO",
    "SOURCE_UPSTREAM_METADATA",
    "SOURCE_ZERO",
    "resolve_upstream_cost_usd",
]
