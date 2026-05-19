"""下游展示价（Playground ``response_cost`` / 日志 snapshot）。"""

from __future__ import annotations

from contextlib import suppress
from decimal import Decimal
from typing import Any

from domains.gateway.application.pricing.pricing_proxy_metadata import (
    downstream_custom_from_metadata,
)
from domains.gateway.application.pricing.upstream_cost_resolver import (
    resolve_upstream_cost_usd,
)


def read_hidden_response_cost_usd(response_obj: Any) -> Decimal | None:
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


def resolve_downstream_display_cost_usd(
    response: Any,
    *,
    metadata: dict[str, Any],
    model: str | None,
) -> Decimal:
    downstream_custom = downstream_custom_from_metadata(metadata)
    if downstream_custom is not None:
        try:
            from litellm import completion_cost

            return Decimal(
                str(
                    completion_cost(
                        completion_response=response,
                        model=model,
                        custom_cost_per_token=downstream_custom,
                    )
                    or 0
                )
            )
        except Exception:
            pass
    hidden = read_hidden_response_cost_usd(response)
    if hidden is not None:
        return hidden
    amount, _source = resolve_upstream_cost_usd(
        response=response,
        model=model,
        metadata=metadata,
    )
    return amount


__all__ = ["read_hidden_response_cost_usd", "resolve_downstream_display_cost_usd"]
