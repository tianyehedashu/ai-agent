"""定价目录管理面辅助（供 reads/writes 调用）。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from domains.gateway.application.pricing.fx_port import FxRatePort
from domains.gateway.application.pricing.money_projector import MoneyProjector
from domains.gateway.application.pricing.pricing_service import PricingService
from domains.gateway.domain.money import DisplayCurrency, MoneyDisplay
from domains.gateway.infrastructure.models.pricing_upstream import UpstreamModelPricing
from domains.gateway.infrastructure.repositories.pricing_repository import (
    DownstreamPricingRepository,
    UpstreamPricingRepository,
)

_MILLION = Decimal("1000000")


def per_million_to_per_token(amount_per_million: Decimal, currency: str, fx: FxRatePort) -> Decimal:
    per_token_display = amount_per_million / _MILLION
    if currency.upper() == "USD":
        return per_token_display
    rate = fx.get_rate("CNY", "USD")
    return per_token_display * rate


def upstream_row_to_response(
    row: UpstreamModelPricing,
    *,
    projector: MoneyProjector,
    currency: DisplayCurrency,
    fx: FxRatePort,
) -> dict[str, Any]:
    inp_disp = projector.project(row.input_cost_per_token, target=currency)
    out_disp = projector.project(row.output_cost_per_token, target=currency)
    return {
        "id": row.id,
        "provider": row.provider,
        "upstream_model": row.upstream_model,
        "capability": row.capability,
        "input_cost_per_token_usd": str(row.input_cost_per_token),
        "output_cost_per_token_usd": str(row.output_cost_per_token),
        "input_cost_per_million_display": MoneyDisplay(
            amount=inp_disp.amount * _MILLION,
            currency=inp_disp.currency,
            fx_rate_used=inp_disp.fx_rate_used,
        ).to_api_dict(),
        "output_cost_per_million_display": MoneyDisplay(
            amount=out_disp.amount * _MILLION,
            currency=out_disp.currency,
            fx_rate_used=out_disp.fx_rate_used,
        ).to_api_dict(),
        "cache_creation_input_token_cost_usd": (
            str(row.cache_creation_input_token_cost)
            if row.cache_creation_input_token_cost is not None
            else None
        ),
        "cache_read_input_token_cost_usd": (
            str(row.cache_read_input_token_cost)
            if row.cache_read_input_token_cost is not None
            else None
        ),
        "effective_from": row.effective_from,
        "effective_to": row.effective_to,
        "version": row.version,
        "source": row.source,
        "display_currency": currency,
        "fx_rate_used": str(fx.get_rate("USD", currency)),
    }


def build_pricing_service(session) -> PricingService:
    return PricingService(
        UpstreamPricingRepository(session),
        DownstreamPricingRepository(session),
    )


def build_money_projector(fx: FxRatePort | None = None) -> MoneyProjector:
    if fx is None:
        from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter

        fx = build_static_fx_adapter()
    return MoneyProjector(fx)


def parse_amount_per_million(
    body: dict[str, Decimal | None], currency: str, fx: FxRatePort
) -> tuple[Decimal, Decimal, Decimal | None, Decimal | None, dict[str, Any]]:
    extra_audit: dict[str, Any] = {
        "input_currency": currency,
        "input_amount_per_million": {},
        "fx_rate_used": str(fx.get_rate("USD", currency) if currency == "CNY" else Decimal("1")),
    }
    inp_raw = body.get("input")
    out_raw = body.get("output")
    if inp_raw is None or out_raw is None:
        raise ValueError("amount_per_million requires input and output")
    inp = per_million_to_per_token(Decimal(str(inp_raw)), currency, fx)
    out = per_million_to_per_token(Decimal(str(out_raw)), currency, fx)
    extra_audit["input_amount_per_million"] = {
        "input": str(inp_raw),
        "output": str(out_raw),
    }
    cache_create = body.get("cache_creation")
    cache_read = body.get("cache_read")
    cc = (
        per_million_to_per_token(Decimal(str(cache_create)), currency, fx)
        if cache_create is not None
        else None
    )
    cr = (
        per_million_to_per_token(Decimal(str(cache_read)), currency, fx)
        if cache_read is not None
        else None
    )
    return inp, out, cc, cr, extra_audit


__all__ = [
    "_MILLION",
    "build_money_projector",
    "build_pricing_service",
    "parse_amount_per_million",
    "upstream_row_to_response",
]
