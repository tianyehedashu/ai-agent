"""MoneyProjector 与 mirror 下游价展示."""

from decimal import Decimal

from domains.gateway.application.pricing.money_projector import MoneyProjector
from domains.gateway.domain.pricing.money import DisplayCurrency


class _FxStub:
    def get_rate(self, base: str, quote: str) -> Decimal:
        if base == "USD" and quote == "CNY":
            return Decimal("7.2")
        raise ValueError(f"unsupported {base}->{quote}")

    def default_display_currency(self) -> DisplayCurrency:
        return "CNY"


def test_project_token_rate_to_cny_per_million() -> None:
    projector = MoneyProjector(_FxStub())
    per_million_usd = Decimal("0.000002") * Decimal("1000000")
    display = projector.project(per_million_usd, target="CNY")
    assert display.currency == "CNY"
    assert Decimal(display.amount) == Decimal("14.4")


def test_project_record_usd_fields() -> None:
    projector = MoneyProjector(_FxStub())
    out = projector.project_record({"input_cost_usd": Decimal("1")}, target="CNY")
    assert out["display_currency"] == "CNY"
    assert Decimal(out["input_cost_display"]["amount"]) == Decimal("7.2")
