"""上游价目键与 Gateway 模型 / LiteLLM 注册表一致性诊断。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.pricing_repository import UpstreamPricingRepository


@dataclass(frozen=True)
class UpstreamPricingAuditReport:
    models_without_upstream: list[str]
    upstream_without_model: list[str]
    registered_upstream_keys: int

    def to_dict(self) -> dict[str, object]:
        return {
            "models_without_upstream": self.models_without_upstream,
            "upstream_without_model": self.upstream_without_model,
            "registered_upstream_keys": self.registered_upstream_keys,
        }


async def audit_upstream_pricing_keys(session: AsyncSession) -> UpstreamPricingAuditReport:
    """对比 ``gateway_models.real_model`` 与活跃 ``upstream_model_pricing``。"""
    models = await GatewayModelRepository(session).list_for_team(None, only_enabled=True)
    upstream_rows = await UpstreamPricingRepository(session).list_active()
    upstream_keys = {
        (r.provider, r.upstream_model, r.capability) for r in upstream_rows if r.upstream_model
    }
    model_keys: set[tuple[str, str, str]] = set()
    models_without: list[str] = []
    for m in models:
        if not m.real_model:
            continue
        cap = str(m.capability or "chat")
        key = (m.provider, m.real_model, cap)
        model_keys.add(key)
        if key not in upstream_keys:
            models_without.append(f"{m.provider}/{m.real_model} ({cap})")

    upstream_without: list[str] = []
    for r in upstream_rows:
        key = (r.provider, r.upstream_model, r.capability)
        if key not in model_keys:
            upstream_without.append(f"{r.provider}/{r.upstream_model} ({r.capability})")

    return UpstreamPricingAuditReport(
        models_without_upstream=sorted(models_without),
        upstream_without_model=sorted(upstream_without),
        registered_upstream_keys=len(upstream_keys),
    )


__all__ = ["UpstreamPricingAuditReport", "audit_upstream_pricing_keys"]
