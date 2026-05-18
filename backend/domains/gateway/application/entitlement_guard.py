"""EntitlementGuard - 下游客户套餐入站校验

ProxyUseCase 在 ``_check_budget`` 之后调用本 guard：
1. 解析 (scope, scope_id, virtual_model, capability)；
2. 选取最匹配的活跃 ``EntitlementPlan`` + 多层 ``EntitlementPlanQuota``；
3. 调 ``QuotaPlanService.check_and_reserve(ns="entitlement")``；
4. 任一桶耗尽 → 抛 ``EntitlementPlanExhaustedError``（HTTP 429）。

设计原则：
- "没有 entitlement plan = 默认放行"，避免与 personal team / system vkey 冲突；
- 失败时返回 ``retry_at`` = 最早分钟桶到期时刻；
- guard 仅做 **资源解析 + 调用 QuotaPlanService**；不持有 Redis 客户端、也不
  导入 ProviderPlan，确保上下游互不依赖。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.entitlement_model_status import ENTITLEMENT_RESETTING_SOON_SECONDS
from domains.gateway.domain.errors import EntitlementPlanExhaustedError
from domains.gateway.domain.quota_plan import (
    ENTITLEMENT_NS,
    PlanQuotaSnapshot,
    PlanQuotaSpec,
    QuotaPlanReservation,
    ResetStrategy,
)
from domains.gateway.domain.types import EntitlementListStatus
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    ENTITLEMENT_SCOPE_APIKEY_GRANT,
    ENTITLEMENT_SCOPE_VKEY,
    EntitlementPlanRepository,
)

if TYPE_CHECKING:
    from domains.gateway.application.quota_plan_service import QuotaPlanService
    from domains.gateway.infrastructure.models.entitlement_plan import (
        EntitlementPlan,
        EntitlementPlanQuota,
    )


@dataclass(frozen=True)
class EntitlementContext:
    """Guard 决策所需的最小上下文，由 ProxyUseCase 装配。"""

    vkey_id: uuid.UUID | None
    apikey_grant_id: uuid.UUID | None
    virtual_model: str | None
    capability: str | None


@dataclass
class EntitlementCheckResult:
    """成功通过时的预扣 token 与 plan 标识，供 ProxyUseCase 在 settle / metadata 阶段使用。"""

    plan_id: uuid.UUID | None
    plan_label: str | None
    specs: list[PlanQuotaSpec]
    reservations: list[QuotaPlanReservation]
    quota_quotas_unit_prices: dict[uuid.UUID, tuple[Decimal | None, Decimal | None]]


_RESET_STRATEGIES: set[ResetStrategy] = {
    "rolling",
    "calendar_daily_utc",
    "calendar_monthly_utc",
    "plan_anniversary",
}


def _reset_strategy(value: str) -> ResetStrategy:
    return value if value in _RESET_STRATEGIES else "rolling"


def _status_from_quota_snapshots(
    snapshots: list[PlanQuotaSnapshot],
    *,
    when: datetime,
) -> EntitlementListStatus:
    if not any(s.exhausted for s in snapshots):
        return "active"
    reset_ats = [
        reset_at
        for s in snapshots
        if s.exhausted
        for reset_at in (s.reset_at(when),)
        if reset_at is not None
    ]
    if reset_ats:
        soonest = min(reset_ats)
        if soonest <= when + timedelta(seconds=ENTITLEMENT_RESETTING_SOON_SECONDS):
            return "resetting"
    return "exhausted"


def _quota_to_spec(row: EntitlementPlanQuota, *, plan: EntitlementPlan) -> PlanQuotaSpec:
    return PlanQuotaSpec(
        quota_id=row.id,
        label=row.label,
        window_seconds=row.window_seconds,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        reset_strategy=_reset_strategy(row.reset_strategy),
        plan_valid_from=plan.valid_from,
    )


class EntitlementGuard:
    """只读+预扣，无 ORM 写。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        quota_service: QuotaPlanService,
    ) -> None:
        self._session = session
        self._repo = EntitlementPlanRepository(session)
        self._quota = quota_service

    async def check_and_reserve(
        self,
        ctx: EntitlementContext,
        *,
        estimate_tokens: int = 0,
        now: datetime | None = None,
    ) -> EntitlementCheckResult:
        """没有匹配 plan = 默认放行；命中 plan 但任一桶耗尽 → 抛错。"""
        when = now or datetime.now(UTC)
        plan = await self._resolve_active_plan(ctx, when=when)
        if plan is None:
            return EntitlementCheckResult(
                plan_id=None,
                plan_label=None,
                specs=[],
                reservations=[],
                quota_quotas_unit_prices={},
            )
        quotas = await self._repo.list_quotas(plan.id)
        specs = [_quota_to_spec(q, plan=plan) for q in quotas]
        if not specs:
            return EntitlementCheckResult(
                plan_id=plan.id,
                plan_label=plan.label,
                specs=[],
                reservations=[],
                quota_quotas_unit_prices={},
            )
        result = await self._quota.check_and_reserve(
            ENTITLEMENT_NS,
            plan.id,
            specs,
            estimate_tokens=estimate_tokens,
            now=when,
        )
        if not result.allowed:
            exhausted = result.exhausted_snapshot
            reset_at_dt = exhausted.reset_at(when) if exhausted is not None else None
            retry_at = reset_at_dt.isoformat() if reset_at_dt is not None else None
            label = exhausted.spec.label if exhausted is not None else "(unknown)"
            reason = exhausted.exhausted_reason or "requests" if exhausted else "requests"
            raise EntitlementPlanExhaustedError(
                plan_id=str(plan.id),
                quota_label=label,
                reason=reason,
                retry_at=retry_at,
            )
        unit_prices: dict[uuid.UUID, tuple[Decimal | None, Decimal | None]] = {
            q.id: (q.unit_price_usd_per_token, q.unit_price_usd_per_request)
            for q in quotas
        }
        return EntitlementCheckResult(
            plan_id=plan.id,
            plan_label=plan.label,
            specs=specs,
            reservations=result.reservations,
            quota_quotas_unit_prices=unit_prices,
        )

    async def commit(
        self,
        plan_id: uuid.UUID,
        specs: list[PlanQuotaSpec],
        *,
        delta_tokens: int,
        delta_usd: Decimal,
        delta_requests: int = 0,
    ) -> None:
        if not specs:
            return
        await self._quota.commit(
            ENTITLEMENT_NS,
            plan_id,
            specs,
            delta_tokens=delta_tokens,
            delta_usd=delta_usd,
            delta_requests=delta_requests,
        )

    async def release(
        self,
        plan_id: uuid.UUID,
        reservations: list[QuotaPlanReservation],
    ) -> None:
        if not reservations:
            return
        await self._quota.release(ENTITLEMENT_NS, plan_id, reservations)

    async def _resolve_active_plan(
        self, ctx: EntitlementContext, *, when: datetime
    ) -> EntitlementPlan | None:
        """优先按 vkey 查；否则按 apikey_grant 查；都没有则返回 None。"""
        if ctx.vkey_id is not None:
            return await self._repo.get_active_for_scope(
                ENTITLEMENT_SCOPE_VKEY,
                ctx.vkey_id,
                virtual_model=ctx.virtual_model,
                capability=ctx.capability,
                now=when,
            )
        if ctx.apikey_grant_id is not None:
            return await self._repo.get_active_for_scope(
                ENTITLEMENT_SCOPE_APIKEY_GRANT,
                ctx.apikey_grant_id,
                virtual_model=ctx.virtual_model,
                capability=ctx.capability,
                now=when,
            )
        return None

    async def status_for_models(
        self,
        scope: str,
        scope_id: uuid.UUID,
        virtual_models: list[str],
        *,
        now: datetime | None = None,
    ) -> dict[str, EntitlementListStatus]:
        """供模型列表注入：返回每个 virtual_model 的 entitlement 状态。

        语义：active / exhausted / resetting / expired / none。
        """
        when = now or datetime.now(UTC)
        plans = await self._repo.list_for_scope(scope, scope_id)
        if not plans:
            return dict.fromkeys(virtual_models, "none")
        active_plans = [
            p
            for p in plans
            if p.is_active and p.valid_from <= when < p.valid_until
        ]
        result: dict[str, EntitlementListStatus] = {}
        for vm in virtual_models:
            matched: EntitlementPlan | None = None
            for p in active_plans:
                included = list(p.included_models or [])
                if included and vm not in included:
                    continue
                matched = p
                break
            if matched is None:
                # 有过期但没活跃
                if any(p.valid_until <= when for p in plans):
                    result[vm] = "expired"
                else:
                    result[vm] = "none"
                continue
            quotas = await self._repo.list_quotas(matched.id)
            specs = [_quota_to_spec(q, plan=matched) for q in quotas]
            if not specs:
                result[vm] = "active"
                continue
            snapshots = await self._quota.snapshot(ENTITLEMENT_NS, matched.id, specs, now=when)
            result[vm] = _status_from_quota_snapshots(snapshots, when=when)
        return result


def build_entitlement_guard_for_session(session: AsyncSession) -> EntitlementGuard:
    """便捷工厂：构造 ``EntitlementGuard`` 供选择器与代理列表共用。"""
    from domains.gateway.application.quota_plan_service import get_quota_plan_service

    return EntitlementGuard(session, quota_service=get_quota_plan_service())


__all__ = [
    "EntitlementCheckResult",
    "EntitlementContext",
    "EntitlementGuard",
    "build_entitlement_guard_for_session",
]
