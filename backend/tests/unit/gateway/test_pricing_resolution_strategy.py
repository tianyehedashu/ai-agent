"""定价解析策略快照（缓存/ detach 安全）。"""

from decimal import Decimal

from domains.gateway.application.pricing.pricing_resolution_cache import (
    _payload_to_resolved,
    _resolved_to_payload,
)
from domains.gateway.application.pricing.pricing_service import (
    ResolvedPricing,
    resolved_inheritance_strategy,
)
from domains.gateway.domain.pricing.pricing_calculator import PricingRate


def test_resolved_inheritance_strategy_from_downstream_strategy_field() -> None:
    resolved = ResolvedPricing(
        upstream=None,
        downstream=PricingRate(
            input_cost_per_token=Decimal("1"),
            output_cost_per_token=Decimal("2"),
        ),
        downstream_row=None,
        upstream_row=None,
        hit_chain=["tenant", "manual"],
        downstream_strategy="manual",
    )
    assert resolved_inheritance_strategy(resolved) == "manual"


def test_resolved_inheritance_strategy_falls_back_to_hit_chain() -> None:
    resolved = ResolvedPricing(
        upstream=None,
        downstream=PricingRate(
            input_cost_per_token=Decimal("1"),
            output_cost_per_token=Decimal("2"),
        ),
        downstream_row=None,
        upstream_row=None,
        hit_chain=["tenant", "mirror"],
    )
    assert resolved_inheritance_strategy(resolved) == "mirror"


def test_cache_roundtrip_preserves_downstream_strategy() -> None:
    resolved = ResolvedPricing(
        upstream=PricingRate(
            input_cost_per_token=Decimal("0.000001"),
            output_cost_per_token=Decimal("0.000002"),
        ),
        downstream=PricingRate(
            input_cost_per_token=Decimal("0.000001"),
            output_cost_per_token=Decimal("0.000002"),
        ),
        downstream_row=None,
        upstream_row=None,
        hit_chain=["tenant", "mirror"],
        downstream_strategy="mirror",
    )
    payload = _resolved_to_payload(resolved)
    restored = _payload_to_resolved(payload)
    assert resolved_inheritance_strategy(restored) == "mirror"
    assert restored.downstream_strategy == "mirror"
