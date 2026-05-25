"""定价目录读侧投影：ORM / 解析结果 → API dict。"""

from __future__ import annotations

from typing import Any
import uuid

from domains.gateway.application.pricing.fx_port import FxRatePort
from domains.gateway.application.pricing.money_projector import MoneyProjector
from domains.gateway.application.pricing.pricing_management import _MILLION
from domains.gateway.application.pricing.pricing_model_enrichment import PricingModelRef
from domains.gateway.domain.money import DisplayCurrency, MoneyDisplay
from domains.gateway.domain.pricing_calculator import PricingRate
from domains.gateway.infrastructure.models.pricing_downstream import DownstreamModelPricing


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
    provider: str | None = None,
    credential_name: str | None = None,
) -> dict[str, Any]:
    inp_api, out_api = _rate_to_million_displays(rate, projector=projector, currency=currency)
    return {
        "gateway_model_id": gateway_model_id,
        "model_name": model_name,
        "provider": provider,
        "credential_name": credential_name,
        "input_cost_per_million_display": inp_api,
        "output_cost_per_million_display": out_api,
        "inheritance_strategy": inheritance_strategy,
        "display_currency": currency,
    }


def pricing_model_ref_to_api_dict(ref: PricingModelRef) -> dict[str, str | uuid.UUID]:
    return {
        "model_name": ref.model_name,
        "provider": ref.provider,
        "credential_id": ref.credential_id,
        "credential_name": ref.credential_name,
        "registry_kind": ref.registry_kind,
    }


def merge_model_ref_into_payload(
    payload: dict[str, Any],
    ref: PricingModelRef | None,
) -> dict[str, Any]:
    if ref is None:
        return payload
    return {**payload, **pricing_model_ref_to_api_dict(ref)}


def downstream_row_to_response_dict(
    row: DownstreamModelPricing,
    *,
    projector: MoneyProjector,
    currency: DisplayCurrency,
    fx: FxRatePort,
    model_ref: PricingModelRef | None = None,
) -> dict[str, Any]:
    if row.inheritance_strategy == "mirror":
        payload: dict[str, Any] = {
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
        return merge_model_ref_into_payload(payload, model_ref)
    if row.input_cost_per_token is None or row.output_cost_per_token is None:
        raise ValueError("manual downstream row missing token rates")
    inp_d = projector.project(row.input_cost_per_token, target=currency)
    out_d = projector.project(row.output_cost_per_token, target=currency)
    payload = {
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
    return merge_model_ref_into_payload(payload, model_ref)


__all__ = [
    "downstream_row_to_response_dict",
    "merge_model_ref_into_payload",
    "pricing_model_ref_to_api_dict",
    "rate_to_member_price_dict",
]
