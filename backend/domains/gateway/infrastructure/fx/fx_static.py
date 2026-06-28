"""静态汇率：读 Settings / app.toml。"""

from __future__ import annotations

from decimal import Decimal
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from domains.gateway.application.pricing.fx_port import FxRatePort
    from domains.gateway.domain.pricing.money import DisplayCurrency

logger = logging.getLogger(__name__)

_DEFAULT_USD_CNY = Decimal("7.20")


class StaticFxRateAdapter:
    """``gateway_fx_usd_cny`` 配置；缺失时 fallback 7.20 并 warn。"""

    def __init__(self, usd_cny: Decimal | None = None) -> None:
        rate = usd_cny if usd_cny is not None else _DEFAULT_USD_CNY
        if rate <= 0:
            logger.warning("gateway_fx_usd_cny invalid (%s), fallback to 7.20", rate)
            rate = _DEFAULT_USD_CNY
        self._usd_cny = rate

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        at: datetime | None = None,
    ) -> Decimal:
        _ = at
        fc = from_currency.upper()
        tc = to_currency.upper()
        if fc == tc:
            return Decimal("1")
        if fc == "USD" and tc == "CNY":
            return self._usd_cny
        if fc == "CNY" and tc == "USD":
            return Decimal("1") / self._usd_cny
        raise ValueError(f"Unsupported currency pair: {from_currency} -> {to_currency}")

    def default_display_currency(self) -> DisplayCurrency:
        return "CNY"

    def supported_currencies(self) -> list[str]:
        return ["USD", "CNY"]


def build_static_fx_adapter() -> FxRatePort:
    from bootstrap.config import settings

    raw = getattr(settings, "gateway_fx_usd_cny", None)
    if raw is None:
        logger.warning("gateway_fx_usd_cny not set, using default 7.20")
        return StaticFxRateAdapter()
    return StaticFxRateAdapter(Decimal(str(raw)))


__all__ = ["StaticFxRateAdapter", "build_static_fx_adapter"]
