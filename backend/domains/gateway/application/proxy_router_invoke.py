"""Router 调用与 internal direct 降级的共用编排（Chat / 非 Chat）。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from domains.gateway.application.proxy_litellm_client import ProxyLiteLLMClient
from domains.gateway.domain.proxy_policy import is_router_model_miss

if TYPE_CHECKING:
    from domains.gateway.application.proxy_context import ProxyContext
    from domains.gateway.application.proxy_guard import ProxyGuard
    from domains.gateway.domain.proxy_policy import BudgetReservation


async def invoke_router_with_direct_fallback(
    *,
    guard: ProxyGuard,
    litellm: ProxyLiteLLMClient,
    ctx: ProxyContext,
    model: str,
    reservations: list[BudgetReservation],
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
        if is_router_model_miss(exc) and await litellm.should_use_internal_direct_litellm(
            ctx, model
        ):
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
