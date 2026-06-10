"""定价解析缓存：不得跨请求保留 SQLAlchemy ORM 实例。"""

from decimal import Decimal
from unittest.mock import MagicMock

from domains.gateway.application.pricing.pricing_resolution_cache import (
    _local_get,
    _local_set,
    cache_safe_resolved,
    clear_pricing_resolution_cache_for_tests,
    pricing_resolution_cache_key,
)
from domains.gateway.application.pricing.pricing_service import ResolvedPricing
from domains.gateway.domain.pricing_calculator import PricingRate


def test_cache_safe_resolved_strips_orm_rows() -> None:
    upstream_row = MagicMock()
    downstream_row = MagicMock()
    rate = PricingRate(
        input_cost_per_token=Decimal("1"),
        output_cost_per_token=Decimal("2"),
    )
    resolved = ResolvedPricing(
        upstream=rate,
        downstream=rate,
        downstream_row=downstream_row,
        upstream_row=upstream_row,
        hit_chain=["tenant"],
        downstream_strategy="manual",
        upstream_extra={"input_cost_per_image": "0.01"},
    )

    safe = cache_safe_resolved(resolved)

    assert safe.upstream_row is None
    assert safe.downstream_row is None
    assert safe.upstream_extra == {"input_cost_per_image": "0.01"}
    assert safe.hit_chain == ["tenant"]


def test_local_cache_does_not_retain_orm_rows() -> None:
    clear_pricing_resolution_cache_for_tests()
    key = pricing_resolution_cache_key(
        tenant_id=None,
        gateway_model_id=None,
        entitlement_plan_id=None,
        provider="openai",
        upstream_model="gpt-4",
        capability="chat",
    )
    rate = PricingRate(
        input_cost_per_token=Decimal("1"),
        output_cost_per_token=Decimal("2"),
    )
    _local_set(
        key,
        ResolvedPricing(
            upstream=rate,
            downstream=rate,
            downstream_row=MagicMock(),
            upstream_row=MagicMock(),
            hit_chain=["global"],
            upstream_extra=None,
        ),
    )

    cached = _local_get(key)

    assert cached is not None
    assert cached.upstream_row is None
    assert cached.downstream_row is None
    clear_pricing_resolution_cache_for_tests()
