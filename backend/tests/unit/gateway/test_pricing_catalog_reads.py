"""pricing_catalog_reads 投影逻辑。"""

from decimal import Decimal
import uuid

from domains.gateway.application.pricing.fx_port import FxRatePort
from domains.gateway.application.pricing.money_projector import MoneyProjector
from domains.gateway.application.pricing.pricing_catalog_reads import (
    is_pricing_admin,
    resolved_to_admin_view_dict,
)
from domains.gateway.application.pricing.pricing_service import ResolvedPricing
from domains.gateway.domain.pricing.pricing_calculator import PricingRate
from domains.tenancy.domain.management_context import ManagementTeamContext


class _Fx(FxRatePort):
    def get_rate(self, base: str, quote: str) -> Decimal:
        if base == "USD" and quote == "CNY":
            return Decimal("7.2")
        if base == "CNY" and quote == "USD":
            return Decimal("1") / Decimal("7.2")
        return Decimal("1")

    def default_display_currency(self):
        return "CNY"

    def supported_currencies(self):
        return ["USD", "CNY"]


def test_is_pricing_admin() -> None:
    admin = ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="shared",
        team_role="admin",
        user_id=uuid.uuid4(),
        is_platform_admin=False,
    )
    member = ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="shared",
        team_role="member",
        user_id=uuid.uuid4(),
        is_platform_admin=False,
    )
    assert is_pricing_admin(admin) is True
    assert is_pricing_admin(member) is False


def test_resolved_to_admin_view_includes_downstream_and_margin() -> None:
    fx = _Fx()
    projector = MoneyProjector(fx)
    upstream = PricingRate(
        input_cost_per_token=Decimal("0.000001"),
        output_cost_per_token=Decimal("0.000002"),
    )
    downstream = PricingRate(
        input_cost_per_token=Decimal("0.000003"),
        output_cost_per_token=Decimal("0.000004"),
    )
    resolved = ResolvedPricing(
        upstream=upstream,
        downstream=downstream,
        downstream_row=None,
        upstream_row=None,
        hit_chain=["upstream_passthrough"],
    )
    payload = resolved_to_admin_view_dict(
        gateway_model_id=uuid.uuid4(),
        model_name="gpt-test",
        resolved=resolved,
        currency="CNY",
        fx=fx,
        projector=projector,
    )
    assert payload["model_name"] == "gpt-test"
    assert payload["downstream"] is not None
    assert payload["downstream"]["input_cost_per_million_display"] is not None
    assert payload["margin_per_million_display"] is not None
    assert payload["hit_chain"] == ["upstream_passthrough"]
