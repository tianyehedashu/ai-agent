"""读侧金额投影：USD 原值 → 展示币种。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from domains.gateway.application.pricing.fx_port import FxRatePort
from domains.gateway.domain.pricing.money import DisplayCurrency, MoneyDisplay, MoneyUSD


class MoneyProjector:
    def __init__(self, fx: FxRatePort) -> None:
        self._fx = fx

    def project(self, usd: Decimal | MoneyUSD, *, target: DisplayCurrency) -> MoneyDisplay:
        money = usd if isinstance(usd, MoneyUSD) else MoneyUSD(amount=Decimal(str(usd)))
        rate = self._fx.get_rate("USD", target)
        return MoneyDisplay.from_usd(money, fx_rate=rate, target=target)

    def project_record(
        self,
        usd_fields: dict[str, Decimal | str | float],
        *,
        target: DisplayCurrency,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, val in usd_fields.items():
            if not key.endswith("_usd"):
                continue
            base = key[: -len("_usd")]
            disp = self.project(Decimal(str(val)), target=target)
            out[f"{base}_display"] = {
                "amount": str(disp.amount),
                "currency": disp.currency,
                "fx_rate_used": str(disp.fx_rate_used),
            }
        out["display_currency"] = target
        out["fx_rate_used"] = str(self._fx.get_rate("USD", target))
        return out


__all__ = ["MoneyProjector"]
