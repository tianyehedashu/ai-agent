"""静态汇率适配器测试。"""

from decimal import Decimal

import pytest

from domains.gateway.infrastructure.fx.fx_static import StaticFxRateAdapter


@pytest.mark.unit
def test_usd_cny_rate() -> None:
    fx = StaticFxRateAdapter(Decimal("7.2"))
    assert fx.get_rate("USD", "CNY") == Decimal("7.2")


@pytest.mark.unit
def test_invalid_rate_fallback() -> None:
    fx = StaticFxRateAdapter(Decimal("0"))
    assert fx.get_rate("USD", "CNY") == Decimal("7.20")
