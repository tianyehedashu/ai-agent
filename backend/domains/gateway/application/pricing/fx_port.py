"""汇率应用端口（由 infrastructure 实现）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from domains.gateway.domain.money import DisplayCurrency


class FxRatePort(Protocol):
    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        at: datetime | None = None,
    ) -> Decimal:
        """返回 1 单位 from_currency = ? to_currency。"""

    def default_display_currency(self) -> DisplayCurrency: ...

    def supported_currencies(self) -> list[str]: ...


__all__ = ["FxRatePort"]
