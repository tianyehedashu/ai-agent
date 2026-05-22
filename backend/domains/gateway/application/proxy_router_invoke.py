"""Router 调用与 internal direct 降级的共用编排（Chat / 非 Chat）。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from domains.gateway.application.proxy_guard import BudgetReservation
    from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase


async def invoke_router_with_direct_fallback(
    use_case: ProxyUseCase,
    ctx: ProxyContext,
    model: str,
    reservations: list[BudgetReservation],
    *,
    use_direct: bool,
    direct_call: Callable[[], Awaitable[Any]],
    router_call: Callable[[], Awaitable[Any]],
) -> Any:
    """Router 调用；model miss 时回退直连，失败时释放预扣。"""
    try:
        if use_direct:
            return await direct_call()
        return await router_call()
    except Exception as exc:
        guard = use_case.guard
        if use_case._is_router_model_miss(
            exc
        ) and await use_case._should_use_internal_direct_litellm(ctx, model):
            try:
                return await direct_call()
            except Exception:
                await guard.release_budget_reservations(reservations)
                await guard.release_entitlement_reservations(ctx)
                raise
        await guard.release_budget_reservations(reservations)
        await guard.release_entitlement_reservations(ctx)
        raise


__all__ = ["invoke_router_with_direct_fallback"]
