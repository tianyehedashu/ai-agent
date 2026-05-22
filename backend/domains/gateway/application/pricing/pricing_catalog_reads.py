"""定价目录读侧（供 presentation 调用，避免 router 内业务逻辑）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.pricing.fx_port import FxRatePort
from domains.gateway.application.pricing.money_projector import MoneyProjector
from domains.gateway.application.pricing.pricing_management import (
    _MILLION,
    build_money_projector,
    build_pricing_service,
    upstream_row_to_response,
)
from domains.gateway.application.pricing.pricing_service import (
    PricingService,
    RateUnavailableError,
    ResolvedPricing,
    resolved_inheritance_strategy,
)
from domains.gateway.domain.money import DisplayCurrency, MoneyDisplay
from domains.gateway.domain.policies.pricing_visibility import can_view_pricing_cost_fields
from domains.gateway.domain.pricing_calculator import PricingRate
from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter
from domains.gateway.infrastructure.models.pricing_downstream import DownstreamModelPricing
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.application.gateway_model_listing import list_merged_models_for_tenant
from domains.gateway.infrastructure.repositories.pricing_repository import (
    DownstreamPricingRepository,
)
from domains.tenancy.domain.management_context import ManagementTeamContext


def is_pricing_admin(team: ManagementTeamContext) -> bool:
    return can_view_pricing_cost_fields(team)


def _rate_to_million_displays(
    rate: PricingRate,
    *,
    projector: MoneyProjector,
    currency: DisplayCurrency,
) -> tuple[dict[str, str], dict[str, str]]:
    inp_d = projector.project(rate.input_cost_per_token, target=currency)
    out_d = projector.project(rate.output_cost_per_token, target=currency)
    inp_m = MoneyDisplay(
        amount=inp_d.amount * _MILLION,
        currency=inp_d.currency,
        fx_rate_used=inp_d.fx_rate_used,
    )
    out_m = MoneyDisplay(
        amount=out_d.amount * _MILLION,
        currency=out_d.currency,
        fx_rate_used=out_d.fx_rate_used,
    )
    return inp_m.to_api_dict(), out_m.to_api_dict()


def rate_to_member_price_dict(
    *,
    gateway_model_id: uuid.UUID | None,
    model_name: str | None,
    rate: PricingRate,
    inheritance_strategy: str | None,
    projector: MoneyProjector,
    currency: DisplayCurrency,
) -> dict[str, Any]:
    inp_api, out_api = _rate_to_million_displays(rate, projector=projector, currency=currency)
    return {
        "gateway_model_id": gateway_model_id,
        "model_name": model_name,
        "input_cost_per_million_display": inp_api,
        "output_cost_per_million_display": out_api,
        "inheritance_strategy": inheritance_strategy,
        "display_currency": currency,
    }


def downstream_row_to_response_dict(
    row: DownstreamModelPricing,
    *,
    projector: MoneyProjector,
    currency: DisplayCurrency,
    fx: FxRatePort,
) -> dict[str, Any]:
    if row.inheritance_strategy == "mirror":
        return {
            "id": row.id,
            "scope": row.scope,
            "scope_id": row.scope_id,
            "gateway_model_id": row.gateway_model_id,
            "inheritance_strategy": row.inheritance_strategy,
            "effective_from": row.effective_from,
            "effective_to": row.effective_to,
            "version": row.version,
            "display_currency": currency,
        }
    if row.input_cost_per_token is None or row.output_cost_per_token is None:
        raise ValueError("manual downstream row missing token rates")
    inp_d = projector.project(row.input_cost_per_token, target=currency)
    out_d = projector.project(row.output_cost_per_token, target=currency)
    return {
        "id": row.id,
        "scope": row.scope,
        "scope_id": row.scope_id,
        "gateway_model_id": row.gateway_model_id,
        "inheritance_strategy": row.inheritance_strategy,
        "input_cost_per_token_usd": str(row.input_cost_per_token),
        "output_cost_per_token_usd": str(row.output_cost_per_token),
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
        "effective_from": row.effective_from,
        "effective_to": row.effective_to,
        "version": row.version,
        "display_currency": currency,
        "fx_rate_used": str(fx.get_rate("USD", currency)),
    }


def resolved_to_admin_view_dict(
    *,
    gateway_model_id: uuid.UUID,
    model_name: str,
    resolved: ResolvedPricing,
    currency: DisplayCurrency,
    fx: FxRatePort,
    projector: MoneyProjector,
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
        )
    else:
        inp_api, out_api = _rate_to_million_displays(
            resolved.downstream, projector=projector, currency=currency
        )
        downstream = {
            "gateway_model_id": gateway_model_id,
            "inheritance_strategy": resolved_inheritance_strategy(resolved)
            or "upstream_passthrough",
            "input_cost_per_million_display": inp_api,
            "output_cost_per_million_display": out_api,
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

    async def list_downstream(
        self,
        *,
        scope: Literal["global", "tenant", "entitlement_plan"],
        scope_id: uuid.UUID | None,
        currency: DisplayCurrency,
    ) -> list[dict[str, Any]]:
        from domains.gateway.domain.types import normalize_downstream_pricing_scope

        scope_key = normalize_downstream_pricing_scope(scope)
        fx = build_static_fx_adapter()
        projector = build_money_projector(fx)
        repo = DownstreamPricingRepository(self.session)
        rows = await repo.list_for_scope(scope=scope_key, scope_id=scope_id)
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(
                    downstream_row_to_response_dict(
                        row, projector=projector, currency=currency, fx=fx
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
        model = await GatewayModelRepository(self.session).get(gateway_model_id)
        if model is None:
            raise LookupError("model not found")
        resolved = await self._svc().resolve_downstream_rate(
            tenant_id=team.team_id,
            entitlement_plan_id=None,
            gateway_model_id=gateway_model_id,
            provider=model.provider,
            upstream_model=model.real_model,
            capability=model.capability,
        )
        fx = build_static_fx_adapter()
        projector = build_money_projector(fx)
        if is_pricing_admin(team):
            return resolved_to_admin_view_dict(
                gateway_model_id=gateway_model_id,
                model_name=model.name,
                resolved=resolved,
                currency=currency,
                fx=fx,
                projector=projector,
            )
        strategy = resolved_inheritance_strategy(resolved)
        return rate_to_member_price_dict(
            gateway_model_id=gateway_model_id,
            model_name=model.name,
            rate=resolved.downstream,
            inheritance_strategy=strategy,
            projector=projector,
            currency=currency,
        )


__all__ = [
    "PricingCatalogReadService",
    "downstream_row_to_response_dict",
    "is_pricing_admin",
    "rate_to_member_price_dict",
    "resolved_to_admin_view_dict",
]
