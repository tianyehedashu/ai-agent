"""定价预估读侧（与 callback 结算同公式）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.pricing.pricing_management import build_pricing_service
from domains.gateway.domain.pricing_calculator import TokenUsage
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository


async def estimate_usage_cost(
    session: AsyncSession,
    *,
    team_id: uuid.UUID,
    gateway_model_id: uuid.UUID,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    entitlement_plan_hit: bool = False,
    provider_plan_hit: bool = False,
) -> dict[str, object]:
    model = await GatewayModelRepository(session).get(gateway_model_id)
    if model is None:
        raise LookupError("gateway model not found")
    svc = build_pricing_service(session)
    resolved = await svc.resolve_downstream_rate(
        team_id=team_id,
        entitlement_plan_id=None,
        gateway_model_id=gateway_model_id,
        provider=model.provider,
        upstream_model=model.real_model,
        capability=model.capability,
    )
    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
    )
    breakdown = await svc.calculate(
        resolved,
        usage,
        provider_plan_hit=provider_plan_hit,
        entitlement_plan_hit=entitlement_plan_hit,
    )
    return {
        "gateway_model_id": str(gateway_model_id),
        "hit_chain": resolved.hit_chain,
        "upstream_cost_usd": str(breakdown.upstream_cost.amount),
        "downstream_revenue_usd": str(breakdown.downstream_revenue.amount),
        "margin_usd": str(breakdown.margin.amount),
        "rate_snapshot": breakdown.rate_snapshot,
        "disclaimer": "estimate_only",
    }


__all__ = ["estimate_usage_cost"]
