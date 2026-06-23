"""代理入站公共 preflight：模型/能力、限流、预算、entitlement（Chat 与非 Chat 共用）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.preflight_failure_logger import schedule_preflight_failure_log
from domains.gateway.domain.errors import EntitlementPlanExhaustedError
from domains.gateway.application.proxy_context import PlatformBudgetPreflightState
from domains.gateway.domain.proxy_policy import BudgetReservation
from domains.gateway.domain.types import GatewayCapability

if TYPE_CHECKING:
    from domains.gateway.application.proxy_context import ProxyContext
    from domains.gateway.application.proxy_guard import ProxyGuard


@dataclass(frozen=True)
class ProxyInboundPreflightResult:
    """入站护栏通过后的模型与 budget 预扣句柄。"""

    model: str | None
    reservations: list[BudgetReservation]
    resolved: ResolvedModelName | None = None


async def run_proxy_inbound_preflight(
    guard: ProxyGuard,
    ctx: ProxyContext,
    *,
    capability: GatewayCapability,
    model: str | None,
    require_model: bool = False,
    match_registered_capability: bool = True,
    estimate_tokens: int = 0,
) -> ProxyInboundPreflightResult:
    """校验、限流、预算预扣、entitlement 预扣（与具体出站 API 无关）。"""
    ctx.capability = capability
    cleaned = (model or "").strip()
    if require_model and not cleaned:
        raise ValueError("model is required")
    ctx.budget_model = cleaned or None

    try:
        if cleaned:
            guard.check_model(cleaned, ctx)
            resolved = await guard.resolve_and_validate_request_model(
                ctx,
                cleaned,
                match_registered_capability=match_registered_capability,
            )
        else:
            resolved = None
        guard.check_capability(ctx)
        await guard.check_limits(ctx, estimate_tokens=estimate_tokens)
        # 个人工作区模型豁免全部平台配额：Phase1 直接返回空预扣，
        # Phase2（pre_call hook）因无成员+凭据规则自然跳过。
        if await guard.is_platform_budget_exempt(ctx, resolved):
            reservations: list[BudgetReservation] = []
            ctx.platform_budget_preflight = PlatformBudgetPreflightState()
        else:
            reservations = await guard.check_budget(ctx, estimate_tokens=estimate_tokens)
        try:
            await guard.check_entitlement(
                ctx,
                cleaned or None,
                estimate_tokens=estimate_tokens,
            )
        except EntitlementPlanExhaustedError:
            await guard.release_budget_reservations(reservations)
            raise

        return ProxyInboundPreflightResult(
            model=cleaned or None,
            reservations=reservations,
            resolved=resolved,
        )
    except Exception as exc:
        schedule_preflight_failure_log(ctx, exc, model=cleaned or None)
        raise


__all__ = ["ProxyInboundPreflightResult", "run_proxy_inbound_preflight"]
