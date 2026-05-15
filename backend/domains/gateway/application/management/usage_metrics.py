"""Gateway 管理面用量指标纯函数（读侧聚合复用）。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def merge_gateway_usage_slices(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """合并两段用量（如 route_name 直连 + deployment 归因），费用按 Decimal 相加。"""
    ca = a.get("cost_usd", 0)
    cb = b.get("cost_usd", 0)
    da = ca if isinstance(ca, Decimal) else Decimal(str(ca or 0))
    db = cb if isinstance(cb, Decimal) else Decimal(str(cb or 0))
    return {
        "requests": int(a.get("requests", 0)) + int(b.get("requests", 0)),
        "input_tokens": int(a.get("input_tokens", 0)) + int(b.get("input_tokens", 0)),
        "output_tokens": int(a.get("output_tokens", 0)) + int(b.get("output_tokens", 0)),
        "cost_usd": da + db,
    }


__all__ = ["merge_gateway_usage_slices"]
