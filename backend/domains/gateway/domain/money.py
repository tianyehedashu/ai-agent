"""金额值对象：标准货币 USD 与展示货币。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

DisplayCurrency = Literal["CNY", "USD"]


@dataclass(frozen=True)
class MoneyUSD:
    """标准结算货币（USD）。"""

    amount: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))


@dataclass(frozen=True)
class MoneyDisplay:
    """展示用金额（含汇率快照）。"""

    amount: Decimal
    currency: DisplayCurrency
    fx_rate_used: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if not isinstance(self.fx_rate_used, Decimal):
            object.__setattr__(self, "fx_rate_used", Decimal(str(self.fx_rate_used)))

    @classmethod
    def from_usd(
        cls,
        usd: MoneyUSD,
        *,
        fx_rate: Decimal,
        target: DisplayCurrency,
    ) -> MoneyDisplay:
        """USD → 目标展示币种。``fx_rate`` 为 1 USD = fx_rate 目标币（如 CNY 7.2）。"""
        if target == "USD":
            return cls(amount=usd.amount, currency="USD", fx_rate_used=Decimal("1"))
        return cls(
            amount=usd.amount * fx_rate,
            currency=target,
            fx_rate_used=fx_rate,
        )

    def to_api_dict(self) -> dict[str, str]:
        """Presentation 层 Pydantic schema 映射用（避免 Application 依赖 Presentation）。"""
        return {
            "amount": str(self.amount),
            "currency": self.currency,
            "fx_rate_used": str(self.fx_rate_used),
        }


__all__ = ["DisplayCurrency", "MoneyDisplay", "MoneyUSD"]
