"""代理路径预算成本：套餐/Provider 包量不计 USD 预算。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

_PACKAGE_ZERO_COST = frozenset({"entitlement", "provider"})


def proxy_budget_cost_usd(metadata: dict[str, Any], upstream_cost: Decimal) -> Decimal:
    package = metadata.get("gateway_billing_package")
    if package in _PACKAGE_ZERO_COST:
        return Decimal("0")
    return upstream_cost


__all__ = ["proxy_budget_cost_usd"]
