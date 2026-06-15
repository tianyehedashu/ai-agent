"""Router 调用与 internal direct 降级的共用编排（Chat / 非 Chat）。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from domains.gateway.application.proxy_litellm_client import ProxyLiteLLMClient
from domains.gateway.domain.proxy_policy import (
    is_reportable_upstream_proxy_exception,
    is_router_model_miss,
    is_router_unavailable_wrapper,
    resolve_upstream_proxy_exception,
)

if TYPE_CHECKING:
    from domains.gateway.application.proxy_context import ProxyContext
    from domains.gateway.application.proxy_guard import ProxyGuard
    from domains.gateway.domain.proxy_policy import BudgetReservation


async def _surface_router_failure(
    *,
    exc: Exception,
    upstream_probe: Callable[[], Awaitable[Exception | None]] | None,
) -> Exception:
    """Router 聚合失败时尽量还原嵌套或探测到的上游异常。"""
    unwrapped = resolve_upstream_proxy_exception(exc)
    if unwrapped is not None and unwrapped is not exc:
        return unwrapped
    if upstream_probe is not None and is_router_unavailable_wrapper(exc):
        probed = await upstream_probe()
        if probed is not None and is_reportable_upstream_proxy_exception(probed):
            return probed
    return exc


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
    upstream_probe: Callable[[], Awaitable[Exception | None]] | None = None,
) -> Any:
    """Router 调用；model miss 时回退直连，失败时释放预扣并尽量透传上游错误。"""
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
        surfaced = await _surface_router_failure(
            exc=exc,
            upstream_probe=upstream_probe,
        )
        await guard.release_budget_reservations(reservations)
        await guard.release_entitlement_reservations(ctx)
        if surfaced is not exc:
            raise surfaced from exc
        raise


__all__ = ["invoke_router_with_direct_fallback"]
