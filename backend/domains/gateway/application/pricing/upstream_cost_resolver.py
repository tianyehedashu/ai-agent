"""统一上游成本（USD）解析：预算、日志、Playground 共用。

``_hidden_params.response_cost`` 在注入下游价后为**售价**，不可直接作为上游成本。
"""

from __future__ import annotations

from contextlib import suppress
from decimal import Decimal
import logging
from typing import Any

from domains.gateway.application.pricing.pricing_settlement import pricing_rate_from_metadata
from domains.gateway.domain.policies.non_token_cost import (
    capability_default_billing_mode,
    estimate_non_token_cost_from_extra,
)
from domains.gateway.domain.pricing_calculator import TokenUsage, calculate_cost_from_rate

logger = logging.getLogger(__name__)

SOURCE_UPSTREAM_METADATA = "upstream_metadata"
SOURCE_LITELLM_HIDDEN = "litellm_hidden"
SOURCE_LITELLM_SLO = "litellm_slo"
SOURCE_LITELLM_COMPLETION = "litellm_completion"
SOURCE_DOMAIN_FALLBACK = "domain_fallback"
SOURCE_PER_REQUEST = "per_request"
SOURCE_NON_TOKEN_EXTRA = "non_token_extra"
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


def _extract_usage_from_response(response_obj: Any, *, requests: int = 1) -> TokenUsage:
    if response_obj is None:
        return TokenUsage(requests=requests)
    usage = getattr(response_obj, "usage", None)
    if usage is None and isinstance(response_obj, dict):
        usage = response_obj.get("usage")
    if usage is None:
        return TokenUsage(requests=requests)
    if isinstance(usage, dict):
        return TokenUsage(
            input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            cache_read_tokens=int(
                usage.get("cache_read_input_tokens") or usage.get("cached_tokens") or 0
            ),
            cache_creation_tokens=int(usage.get("cache_creation_input_tokens") or 0),
            requests=requests,
        )
    return TokenUsage(
        input_tokens=int(
            getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0
        ),
        output_tokens=int(
            getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0
        ),
        cache_read_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        cache_creation_tokens=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        requests=requests,
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
    requests: int = 1,
) -> tuple[Decimal, str]:
    """返回 (上游成本 USD, source_tag)。"""
    downstream_applied = _has_downstream_pricing(metadata)
    capability = str(metadata.get("gateway_capability", "")).strip()
    billing_mode = capability_default_billing_mode(capability) if capability else "token"

    upstream_custom = metadata.get("gateway_pricing_upstream")
    upstream_dict = upstream_custom if isinstance(upstream_custom, dict) else None
    has_upstream_token_rates = (
        isinstance(upstream_dict, dict)
        and upstream_dict.get("input_cost_per_token") is not None
        and upstream_dict.get("output_cost_per_token") is not None
    )

    if isinstance(upstream_dict, dict):
        per_request_raw = upstream_dict.get("per_request_usd")
        if per_request_raw is not None:
            per_request = Decimal(str(per_request_raw)) * Decimal(requests)
            if per_request > 0:
                return per_request, SOURCE_PER_REQUEST

        inp = upstream_dict.get("input_cost_per_token")
        out = upstream_dict.get("output_cost_per_token")
        if inp is not None and out is not None:
            cost = _completion_cost_upstream(
                response,
                model=model,
                custom_cost_per_token=upstream_dict,
            )
            if cost is not None and cost > 0:
                return cost, SOURCE_UPSTREAM_METADATA

        extra_cost = estimate_non_token_cost_from_extra(
            upstream_dict,
            response,
            requests=requests,
        )
        if extra_cost is not None and extra_cost > 0:
            return extra_cost, SOURCE_NON_TOKEN_EXTRA

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
    completion_model = litellm_model or model
    cost: Decimal | None = None
    skip_token_completion = billing_mode == "per_request" and not has_upstream_token_rates
    if completion_model is not None and not skip_token_completion:
        cost = _completion_cost_upstream(
            response, model=completion_model, custom_cost_per_token=None
        )
        if cost is not None and cost > 0:
            return cost, SOURCE_LITELLM_COMPLETION

    if isinstance(upstream_dict, dict):
        rate = pricing_rate_from_metadata(upstream_dict)
        if rate is not None:
            usage = _extract_usage_from_response(response, requests=requests)
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
    "SOURCE_NON_TOKEN_EXTRA",
    "SOURCE_PER_REQUEST",
    "SOURCE_UPSTREAM_METADATA",
    "SOURCE_ZERO",
    "resolve_upstream_cost_usd",
]
