"""定价目录读侧（供 presentation 调用，避免 router 内业务逻辑）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.gateway_model_listing import list_merged_models_for_tenant
from domains.gateway.application.pricing.fx_port import FxRatePort
from domains.gateway.application.pricing.money_projector import MoneyProjector
from domains.gateway.application.pricing.pricing_management import (
    build_money_projector,
    build_pricing_service,
    upstream_row_to_response,
)
from domains.gateway.application.pricing.pricing_model_enrichment import (
    PricingModelRef,
    build_credential_name_map_for_models,
    build_pricing_model_ref_map,
    resolve_pricing_model_ref,
)
from domains.gateway.application.pricing.pricing_read_mappers import (
    downstream_row_to_response_dict,
    rate_to_member_price_dict,
)
from domains.gateway.application.pricing.pricing_service import (
    PricingService,
    RateUnavailableError,
    ResolvedPricing,
    resolved_inheritance_strategy,
)
from domains.gateway.domain.money import DisplayCurrency, MoneyDisplay
from domains.gateway.domain.policies.pricing_visibility import can_view_pricing_cost_fields
from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter
from domains.gateway.infrastructure.models.pricing_downstream import DownstreamModelPricing
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.pricing_repository import (
    DownstreamPricingRepository,
)
from domains.tenancy.domain.management_context import ManagementTeamContext


def is_pricing_admin(team: ManagementTeamContext) -> bool:
    return can_view_pricing_cost_fields(team)


def _tenant_id_for_scope(
    scope: Literal["global", "tenant", "entitlement_plan"],
    scope_id: uuid.UUID | None,
) -> uuid.UUID | None:
    if scope == "tenant" and scope_id is not None:
        return scope_id
    return None


def resolved_to_admin_view_dict(
    *,
    gateway_model_id: uuid.UUID,
    model_name: str,
    resolved: ResolvedPricing,
    currency: DisplayCurrency,
    fx: FxRatePort,
    projector: MoneyProjector,
    model_ref: PricingModelRef | None = None,
) -> dict[str, Any]:
    upstream = (
        upstream_row_to_response(
            resolved.upstream_row,
            projector=projector,
            currency=currency,
            fx=fx,
        )
        if resolved.upstream_row is not None
        else None
    )
    downstream: dict[str, Any] | None = None
    if resolved.downstream_row is not None:
        downstream = downstream_row_to_response_dict(
            resolved.downstream_row,
            projector=projector,
            currency=currency,
            fx=fx,
            model_ref=model_ref,
        )
    else:
        from domains.gateway.application.pricing.pricing_management import _MILLION

        inp_d = projector.project(resolved.downstream.input_cost_per_token, target=currency)
        out_d = projector.project(resolved.downstream.output_cost_per_token, target=currency)
        downstream = {
            "gateway_model_id": gateway_model_id,
            "inheritance_strategy": resolved_inheritance_strategy(resolved)
            or "upstream_passthrough",
            "input_cost_per_million_display": MoneyDisplay(
                amount=inp_d.amount * _MILLION,
                currency=inp_d.currency,
                fx_rate_used=inp_d.fx_rate_used,
            ).to_api_dict(),
            "output_cost_per_million_display": MoneyDisplay(
                amount=out_d.amount * _MILLION,
                currency=out_d.currency,
                fx_rate_used=out_d.fx_rate_used,
            ).to_api_dict(),
            "display_currency": currency,
        }
    margin_display: dict[str, str] | None = None
    if resolved.upstream is not None:
        margin_in = (
            resolved.downstream.input_cost_per_token - resolved.upstream.input_cost_per_token
        )
        margin_out = (
            resolved.downstream.output_cost_per_token - resolved.upstream.output_cost_per_token
        )
        margin_disp = projector.project(margin_in + margin_out, target=currency)
        margin_display = MoneyDisplay(
            amount=margin_disp.amount * _MILLION,
            currency=margin_disp.currency,
            fx_rate_used=margin_disp.fx_rate_used,
        ).to_api_dict()
    return {
        "gateway_model_id": gateway_model_id,
        "model_name": model_name,
        "downstream": downstream,
        "upstream": upstream,
        "margin_per_million_display": margin_display,
        "hit_chain": resolved.hit_chain,
    }


@dataclass
class PricingCatalogReadService:
    session: AsyncSession

    def _svc(self) -> PricingService:
        return build_pricing_service(self.session)

    async def list_effective_providers(self) -> list[dict[str, str | int | bool]]:
        summaries = await ProviderCredentialRepository(
            self.session
        ).list_effective_provider_summaries()
        return [
            {
                "provider": s.provider,
                "credential_count": s.credential_count,
                "has_managed": s.has_managed,
                "has_user": s.has_user,
            }
            for s in summaries
        ]

    async def downstream_row_to_enriched_response(
        self,
        row: DownstreamModelPricing,
        *,
        currency: DisplayCurrency,
        tenant_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        fx = build_static_fx_adapter()
        projector = build_money_projector(fx)
        model_ref: PricingModelRef | None = None
        if row.gateway_model_id is not None:
            ref_map = await build_pricing_model_ref_map(
                self.session,
                {row.gateway_model_id},
                tenant_id=tenant_id,
            )
            model_ref = ref_map.get(row.gateway_model_id)
        return downstream_row_to_response_dict(
            row,
            projector=projector,
            currency=currency,
            fx=fx,
            model_ref=model_ref,
        )

    async def list_downstream(
        self,
        *,
        scope: Literal["global", "tenant", "entitlement_plan"],
        scope_id: uuid.UUID | None,
        currency: DisplayCurrency,
    ) -> list[dict[str, Any]]:
        from domains.gateway.domain.types import normalize_downstream_pricing_scope

        scope_key = normalize_downstream_pricing_scope(scope)
        tenant_id = _tenant_id_for_scope(scope_key, scope_id)
        fx = build_static_fx_adapter()
        projector = build_money_projector(fx)
        repo = DownstreamPricingRepository(self.session)
        rows = await repo.list_for_scope(scope=scope_key, scope_id=scope_id)
        model_ids = {r.gateway_model_id for r in rows if r.gateway_model_id is not None}
        ref_map = await build_pricing_model_ref_map(
            self.session,
            model_ids,
            tenant_id=tenant_id,
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                model_ref = (
                    ref_map.get(row.gateway_model_id)
                    if row.gateway_model_id is not None
                    else None
                )
                out.append(
                    downstream_row_to_response_dict(
                        row,
                        projector=projector,
                        currency=currency,
                        fx=fx,
                        model_ref=model_ref,
                    )
                )
            except ValueError:
                continue
        return out

    async def list_my_prices(
        self,
        *,
        team_id: uuid.UUID,
        user_id: uuid.UUID | None,
        currency: DisplayCurrency,
    ) -> list[dict[str, Any]]:
        fx = build_static_fx_adapter()
        projector = build_money_projector(fx)
        svc = self._svc()
        models = await list_merged_models_for_tenant(
            self.session,
            team_id,
            only_enabled=True,
            user_id=user_id,
        )
        cred_names = await build_credential_name_map_for_models(self.session, models)
        out: list[dict[str, Any]] = []
        for model in models:
            try:
                resolved = await svc.resolve_downstream_rate(
                    tenant_id=team_id,
                    entitlement_plan_id=None,
                    gateway_model_id=model.id,
                    provider=model.provider,
                    upstream_model=model.real_model,
                    capability=model.capability,
                )
            except RateUnavailableError:
                continue
            strategy = resolved_inheritance_strategy(resolved) or "upstream_passthrough"
            out.append(
                rate_to_member_price_dict(
                    gateway_model_id=model.id,
                    model_name=model.name,
                    rate=resolved.downstream,
                    inheritance_strategy=strategy,
                    projector=projector,
                    currency=currency,
                    provider=model.provider,
                    credential_name=cred_names.get(model.credential_id),
                )
            )
        return out

    async def resolve_for_team(
        self,
        *,
        team: ManagementTeamContext,
        gateway_model_id: uuid.UUID,
        currency: DisplayCurrency,
    ) -> dict[str, Any]:
        model_ref = await resolve_pricing_model_ref(
            self.session,
            gateway_model_id,
            tenant_id=team.team_id,
        )
        if model_ref is None:
            raise LookupError("model not found")
        resolved = await self._svc().resolve_downstream_rate(
            tenant_id=team.team_id,
            entitlement_plan_id=None,
            gateway_model_id=gateway_model_id,
            provider=model_ref.provider,
            upstream_model=model_ref.real_model,
            capability=model_ref.capability,
        )
        fx = build_static_fx_adapter()
        projector = build_money_projector(fx)
        if is_pricing_admin(team):
            return resolved_to_admin_view_dict(
                gateway_model_id=gateway_model_id,
                model_name=model_ref.model_name,
                resolved=resolved,
                currency=currency,
                fx=fx,
                projector=projector,
                model_ref=model_ref,
            )
        strategy = resolved_inheritance_strategy(resolved)
        return rate_to_member_price_dict(
            gateway_model_id=gateway_model_id,
            model_name=model_ref.model_name,
            rate=resolved.downstream,
            inheritance_strategy=strategy,
            projector=projector,
            currency=currency,
            provider=model_ref.provider,
            credential_name=model_ref.credential_name,
        )


__all__ = [
    "PricingCatalogReadService",
    "downstream_row_to_response_dict",
    "is_pricing_admin",
    "rate_to_member_price_dict",
    "resolved_to_admin_view_dict",
]
