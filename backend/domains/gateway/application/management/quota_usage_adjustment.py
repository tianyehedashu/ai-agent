"""配额用量手工校正（管理面写路径）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
import uuid

from domains.gateway.application.budget_service import BudgetService
from domains.gateway.application.management.budget_usage_reads import (
    BudgetWindowLookup,
    resolve_budget_window_key,
)
from domains.gateway.application.management.plan_read_mappers import (
    entitlement_plan_quota_to_spec,
    provider_plan_quota_to_spec,
)
from domains.gateway.application.management.quota_plan_usage_reads import (
    QuotaWindowLookup,
    resolve_quota_window_key,
)
from domains.gateway.application.quota_plan_service import get_quota_plan_service
from domains.gateway.domain.period_reset_anchor import (
    PeriodResetAnchor,
    period_reset_anchor_from_plan_quota,
    period_reset_anchor_from_row,
)
from domains.gateway.domain.quota_plan import (
    ENTITLEMENT_NS,
    PLATFORM_NS,
    PROVIDER_NS,
    PlanQuotaSpec,
    QuotaPlanNamespace,
    is_sliding_rolling_window,
)
from domains.gateway.infrastructure.models.provider_plan import ProviderPlanQuota
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    EntitlementPlanRepository,
)
from domains.gateway.infrastructure.repositories.provider_plan_repository import (
    ProviderPlanRepository,
)
from domains.gateway.infrastructure.repositories.quota_plan_usage_bucket_repository import (
    QuotaPlanUsageBucketRepository,
)
from libs.exceptions import NotFoundError, ValidationError

QuotaUsageAdjustmentMode = Literal["set", "reset_window"]


@dataclass(frozen=True)
class QuotaUsageAdjustmentCommand:
    layer: Literal["platform", "upstream", "downstream"]
    budget_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    quota_id: uuid.UUID | None = None
    mode: QuotaUsageAdjustmentMode = "set"
    current_usd: Decimal | None = None
    current_tokens: int | None = None
    current_requests: int | None = None


def _resolved_usage_values(
    cmd: QuotaUsageAdjustmentCommand,
) -> tuple[Decimal, int, int]:
    if cmd.mode == "reset_window":
        return Decimal("0"), 0, 0
    if cmd.current_usd is None and cmd.current_tokens is None and cmd.current_requests is None:
        raise ValidationError("set 模式至少填写一项已用额度")
    return (
        cmd.current_usd if cmd.current_usd is not None else Decimal("0"),
        cmd.current_tokens if cmd.current_tokens is not None else 0,
        cmd.current_requests if cmd.current_requests is not None else 0,
    )


@dataclass(frozen=True)
class _PlanQuotaContext:
    ns: QuotaPlanNamespace
    window_seconds: int
    reset_strategy: str
    anchor: PeriodResetAnchor
    plan_valid_from: datetime | None
    quota_spec: PlanQuotaSpec


async def _load_plan_quota_context(
    session: object,
    layer: Literal["upstream", "downstream"],
    plan_id: uuid.UUID,
    quota_id: uuid.UUID,
) -> _PlanQuotaContext:
    """加载上游 / 下游套餐配额上下文（两层仅仓储与命名空间不同，去重收敛于此）。"""
    if layer == "upstream":
        plan_repo: ProviderPlanRepository | EntitlementPlanRepository = ProviderPlanRepository(
            session
        )
        ns: QuotaPlanNamespace = PROVIDER_NS
        noun = "上游"
    else:
        plan_repo = EntitlementPlanRepository(session)
        ns = ENTITLEMENT_NS
        noun = "下游"

    plan = await plan_repo.get(plan_id)
    if plan is None:
        raise NotFoundError(f"{noun}套餐不存在: {plan_id}")
    quotas = await plan_repo.list_quotas(plan_id)
    quota = next((q for q in quotas if q.id == quota_id), None)
    if quota is None:
        raise NotFoundError(f"{noun}配额不存在: {quota_id}")

    quota_spec = (
        provider_plan_quota_to_spec(quota, plan_valid_from=plan.valid_from)
        if isinstance(quota, ProviderPlanQuota)
        else entitlement_plan_quota_to_spec(quota, plan_valid_from=plan.valid_from)
    )
    return _PlanQuotaContext(
        ns=ns,
        window_seconds=quota.window_seconds,
        reset_strategy=quota.reset_strategy,
        anchor=period_reset_anchor_from_plan_quota(
            reset_timezone=quota.reset_timezone,
            reset_time_minutes=quota.reset_time_minutes,
            reset_day_of_month=quota.reset_day_of_month,
        ),
        plan_valid_from=plan.valid_from,
        quota_spec=quota_spec,
    )


async def apply_quota_usage_adjustment(
    session: object,
    cmd: QuotaUsageAdjustmentCommand,
) -> None:
    """写入 PG 汇总桶并同步 Redis 执法桶（platform / plan 全层一致）。"""
    from sqlalchemy.ext.asyncio import AsyncSession

    if not isinstance(session, AsyncSession):
        raise TypeError("session must be AsyncSession")

    cost_usd, tokens, requests = _resolved_usage_values(cmd)
    now = datetime.now(UTC)
    bucket_repo = QuotaPlanUsageBucketRepository(session)

    if cmd.layer == "platform":
        if cmd.budget_id is None:
            raise ValidationError("platform 用量校正需要 budget_id")
        budget = await BudgetRepository(session).get(cmd.budget_id)
        if budget is None:
            raise NotFoundError(f"预算不存在: {cmd.budget_id}")

        anchor = period_reset_anchor_from_row(
            timezone=budget.period_timezone,
            time_minutes=budget.period_reset_minutes,
            day_of_month=budget.period_reset_day,
        )
        lookup = BudgetWindowLookup(
            budget_id=budget.id,
            period=budget.period,
            target_kind=budget.target_kind,
            target_id=budget.target_id,
            model_name=budget.model_name,
            credential_id=budget.credential_id,
            tenant_id=budget.tenant_id,
            period_reset_anchor=anchor,
        )
        window_key = resolve_budget_window_key(lookup, now=now)
        await bucket_repo.set_bucket(
            PLATFORM_NS,
            budget.id,
            budget.id,
            window_key.window_start,
            tokens=tokens,
            requests=requests,
            cost_usd=cost_usd,
        )
        await BudgetService().set_budget_usage(
            target_kind=budget.target_kind,
            target_id=str(budget.target_id) if budget.target_id is not None else None,
            period=budget.period,
            cost=cost_usd,
            tokens=tokens,
            requests=requests,
            budget_model_name=budget.model_name,
            credential_id=budget.credential_id,
            tenant_id=budget.tenant_id,
            period_reset_anchor=anchor,
        )
        await BudgetRepository(session).set_usage(
            budget.id,
            current_usd=cost_usd,
            current_tokens=tokens,
            current_requests=requests,
        )
        return

    if cmd.plan_id is None or cmd.quota_id is None:
        raise ValidationError(f"{cmd.layer} 用量校正需要 plan_id 与 quota_id")

    ctx = await _load_plan_quota_context(session, cmd.layer, cmd.plan_id, cmd.quota_id)
    ns = ctx.ns
    window_seconds = ctx.window_seconds
    reset_strategy = ctx.reset_strategy
    anchor = ctx.anchor
    plan_valid_from = ctx.plan_valid_from

    # 真正的滚动窗口（window_seconds>0 且 rolling）用量由请求日志实时统计（展示读忽略
    # PG 桶），手工校正 / 清零写桶不会反映到展示，徒增误解，直接拒绝并引导改固定周期。
    # 注意：window_seconds<=0 的累计（总额）即便策略名是 rolling 也按固定累计，允许校正。
    if is_sliding_rolling_window(window_seconds, reset_strategy):
        raise ValidationError(
            "滚动窗口配额用量由请求日志实时统计，不支持手工校正 / 清零；"
            "如需可校正 / 到点重置，请将该配额改为每日 / 每月固定周期。"
        )

    lookup = QuotaWindowLookup(
        ns=ns,
        plan_id=cmd.plan_id,
        quota_id=cmd.quota_id,
        window_seconds=window_seconds,
        reset_strategy=reset_strategy,
        plan_valid_from=plan_valid_from,
        period_reset_anchor=anchor,
    )
    window_key = resolve_quota_window_key(lookup, now=now)
    await bucket_repo.set_bucket(
        ns,
        cmd.plan_id,
        cmd.quota_id,
        window_key.window_start,
        tokens=tokens,
        requests=requests,
        cost_usd=cost_usd,
    )
    await get_quota_plan_service().set_window_usage(
        ns,
        cmd.plan_id,
        ctx.quota_spec,
        cost_usd=cost_usd,
        tokens=tokens,
        requests=requests,
        now=now,
    )


__all__ = [
    "QuotaUsageAdjustmentCommand",
    "QuotaUsageAdjustmentMode",
    "apply_quota_usage_adjustment",
]
