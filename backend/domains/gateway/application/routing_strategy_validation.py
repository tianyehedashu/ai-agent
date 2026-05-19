"""GatewayRoute / multi-credential 的 LiteLLM routing_strategy 校验。"""

from __future__ import annotations

from domains.gateway.domain.types import RoutingStrategy
from libs.exceptions import ValidationError


def validate_routing_strategy(strategy: str) -> str:
    """返回规范化策略字面量；非法时抛 ``ValidationError``。"""
    raw = (strategy or "").strip()
    if not raw:
        raise ValidationError("routing strategy 不能为空")
    try:
        return RoutingStrategy(raw).value
    except ValueError:
        allowed = ", ".join(s.value for s in RoutingStrategy)
        raise ValidationError(f"不支持的 routing strategy: {raw!r}（允许: {allowed}）") from None


__all__ = ["validate_routing_strategy"]
