"""Budget / Plan → 配额规则读模型投影（application 层，无 I/O）。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from domains.gateway.application.management.quota_rule_read_model import (
    QuotaRuleKey,
    QuotaRuleLayer,
    QuotaRuleLimits,
    QuotaRuleReadModel,
    QuotaRuleSourceRef,
    QuotaRuleUsage,
)
from domains.gateway.domain.period_reset_anchor import (
    compute_period_reset_at,
    compute_period_window_start,
    period_reset_anchor_from_plan_quota,
    period_reset_anchor_from_row,
)
from domains.gateway.domain.quota_plan import (
    compute_reset_at,
    compute_window_start_datetime,
    compute_window_start_minute,
    normalize_reset_strategy,
)

if TYPE_CHECKING:
    from typing import Literal

    from domains.gateway.application.management.plan_read_models import (
        EntitlementPlanReadModel,
        PlanQuotaReadModel,
        ProviderPlanReadModel,
    )
    from domains.gateway.infrastructure.models.budget import GatewayBudget


def budget_to_quota_rule(
    budget: GatewayBudget,
    *,
    team_id: UUID,
) -> QuotaRuleReadModel:
    user_id: UUID | None = None
    access_kind: Literal["none", "vkey", "apikey_grant"] = "none"
    access_id: UUID | None = None
    target_kind = budget.target_kind
    target_id = budget.target_id

    if budget.target_kind == "user":
        user_id = budget.target_id
    elif budget.target_kind == "key":
        access_kind = "vkey"
        access_id = budget.target_id
    elif budget.target_kind in ("tenant", "system"):
        user_id = None

    anchor = period_reset_anchor_from_row(
        timezone=budget.period_timezone,
        time_minutes=budget.period_reset_minutes,
        day_of_month=budget.period_reset_day,
    )
    now = datetime.now(UTC)
    window_start = compute_period_window_start(now, budget.period, anchor)
    reset_at = compute_period_reset_at(now, budget.period, anchor)

    key = QuotaRuleKey(
        team_id=team_id,
        layer="platform",
        user_id=user_id,
        credential_id=budget.credential_id,
        model_name=budget.model_name,
        period=budget.period,
        window_seconds=None,
        reset_strategy=None,
        period_timezone=anchor.timezone,
        period_reset_minutes=anchor.time_minutes,
        period_reset_day=anchor.day_of_month,
        access_kind=access_kind,
        access_id=access_id,
        quota_label=None,
        target_kind=target_kind,
        target_id=target_id,
    )
    return QuotaRuleReadModel(
        key=key,
        source_ref=QuotaRuleSourceRef(layer="platform", budget_id=budget.id),
        limits=QuotaRuleLimits(
            limit_usd=budget.limit_usd,
            soft_limit_usd=budget.soft_limit_usd,
            limit_tokens=budget.limit_tokens,
            limit_requests=budget.limit_requests,
        ),
        usage=QuotaRuleUsage(
            window_start=window_start,
            reset_at=reset_at,
            budget_reset_at=reset_at,
        ),
        plan_label=None,
        is_active=True,
    )


def _plan_quota_limits(quota: PlanQuotaReadModel) -> QuotaRuleLimits:
    return QuotaRuleLimits(
        limit_usd=quota.limit_usd,
        soft_limit_usd=None,
        limit_tokens=quota.limit_tokens,
        limit_requests=quota.limit_requests,
        unit_price_usd_per_token=quota.unit_price_usd_per_token,
        unit_price_usd_per_request=quota.unit_price_usd_per_request,
    )


def _plan_quota_key_fields(quota: PlanQuotaReadModel) -> dict[str, object]:
    return {
        "period_timezone": quota.reset_timezone,
        "period_reset_minutes": quota.reset_time_minutes,
        "period_reset_day": quota.reset_day_of_month,
    }


def _plan_quota_period_bounds(
    quota: PlanQuotaReadModel,
    *,
    plan_valid_from: datetime | None,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """当前窗口起点与下次重置时刻（只读展示）。"""
    when = now or datetime.now(UTC)
    window_seconds = quota.window_seconds
    strategy = normalize_reset_strategy(quota.reset_strategy)
    anchor = period_reset_anchor_from_plan_quota(
        reset_timezone=quota.reset_timezone,
        reset_time_minutes=quota.reset_time_minutes,
        reset_day_of_month=quota.reset_day_of_month,
    )
    if window_seconds <= 0:
        window_start = compute_window_start_datetime(
            when,
            window_seconds,
            strategy=strategy,
            plan_valid_from=plan_valid_from,
            period_reset_anchor=anchor,
        )
        return window_start, None
    if strategy == "rolling":
        # 滚动窗口随时间连续滑动、无固定重置时刻。窗口起点 = now - 窗口长度，
        # reset_at 置空（旧实现误把窗口起点当作最早用量分钟，恒得出 ≈ now，
        # 在 UI 上永远显示成「刚到期」）。
        window_start = compute_window_start_datetime(
            when,
            window_seconds,
            strategy=strategy,
            plan_valid_from=plan_valid_from,
            period_reset_anchor=anchor,
        )
        return window_start, None
    minute_idx = compute_window_start_minute(
        when,
        window_seconds,
        strategy=strategy,
        plan_valid_from=plan_valid_from,
        period_reset_anchor=anchor,
    )
    window_start = compute_window_start_datetime(
        when,
        window_seconds,
        strategy=strategy,
        plan_valid_from=plan_valid_from,
        period_reset_anchor=anchor,
    )
    reset_at = compute_reset_at(
        strategy=strategy,
        window_seconds=window_seconds,
        now=when,
        earliest_minute_in_window=minute_idx,
        plan_valid_from=plan_valid_from,
        period_reset_anchor=anchor,
    )
    return window_start, reset_at


def _plan_quota_usage_hint(
    quota: PlanQuotaReadModel,
    *,
    plan_valid_from: datetime | None,
) -> QuotaRuleUsage | None:
    window_start, reset_at = _plan_quota_period_bounds(quota, plan_valid_from=plan_valid_from)
    if window_start is None and reset_at is None:
        return None
    return QuotaRuleUsage(
        current_tokens=None,
        current_requests=None,
        current_usd=None,
        window_start=window_start,
        reset_at=reset_at,
        budget_reset_at=reset_at,
    )


def flatten_provider_plan(
    plan: ProviderPlanReadModel,
    *,
    team_id: UUID,
) -> list[QuotaRuleReadModel]:
    rules: list[QuotaRuleReadModel] = []
    for quota in plan.quotas:
        key = QuotaRuleKey(
            team_id=team_id,
            layer="upstream",
            user_id=None,
            credential_id=plan.credential_id,
            model_name=plan.real_model,
            period=None,
            window_seconds=quota.window_seconds,
            reset_strategy=quota.reset_strategy,
            **_plan_quota_key_fields(quota),
            access_kind="none",
            access_id=None,
            quota_label=quota.label,
            target_kind=None,
            target_id=None,
        )
        rules.append(
            QuotaRuleReadModel(
                key=key,
                source_ref=QuotaRuleSourceRef(
                    layer="upstream",
                    plan_id=plan.id,
                    quota_id=quota.id,
                ),
                limits=_plan_quota_limits(quota),
                usage=_plan_quota_usage_hint(quota, plan_valid_from=plan.valid_from),
                plan_label=plan.label,
                is_active=plan.is_active,
                plan_valid_from=plan.valid_from,
            )
        )
    return rules


def flatten_entitlement_plan(
    plan: EntitlementPlanReadModel,
    *,
    team_id: UUID,
) -> list[QuotaRuleReadModel]:
    access_kind: Literal["none", "vkey", "apikey_grant"]
    if plan.scope == "vkey":
        access_kind = "vkey"
    elif plan.scope == "apikey_grant":
        access_kind = "apikey_grant"
    else:
        access_kind = "none"

    if len(plan.included_models) == 1:
        model_name = plan.included_models[0]
    elif len(plan.included_models) == 0:
        model_name = None
    else:
        model_name = plan.included_models[0]

    rules: list[QuotaRuleReadModel] = []
    for quota in plan.quotas:
        key = QuotaRuleKey(
            team_id=team_id,
            layer="downstream",
            user_id=None,
            credential_id=None,
            model_name=model_name,
            period=None,
            window_seconds=quota.window_seconds,
            reset_strategy=quota.reset_strategy,
            **_plan_quota_key_fields(quota),
            access_kind=access_kind,
            access_id=plan.scope_id,
            quota_label=quota.label,
            target_kind=None,
            target_id=None,
        )
        rules.append(
            QuotaRuleReadModel(
                key=key,
                source_ref=QuotaRuleSourceRef(
                    layer="downstream",
                    plan_id=plan.id,
                    quota_id=quota.id,
                ),
                limits=_plan_quota_limits(quota),
                usage=_plan_quota_usage_hint(quota, plan_valid_from=plan.valid_from),
                plan_label=plan.label,
                is_active=plan.is_active,
                plan_valid_from=plan.valid_from,
            )
        )
    return rules


def filter_quota_rules(
    rules: list[QuotaRuleReadModel],
    *,
    layer: QuotaRuleLayer | None = None,
    user_id: UUID | None = None,
    credential_id: UUID | None = None,
    model_name: str | None = None,
    period: str | None = None,
) -> list[QuotaRuleReadModel]:
    result = rules
    if layer is not None:
        result = [r for r in result if r.key.layer == layer]
    if user_id is not None:
        result = [
            r
            for r in result
            if r.key.user_id == user_id or (r.key.user_id is None and r.key.layer == "platform")
        ]
    if credential_id is not None:
        result = [r for r in result if r.key.credential_id == credential_id]
    if model_name is not None:
        normalized = model_name.strip()
        result = [r for r in result if r.key.model_name == normalized or r.key.model_name is None]
    if period is not None:
        result = [
            r
            for r in result
            if r.key.period == period or (r.key.period is None and r.key.window_seconds is not None)
        ]
    return result


__all__ = [
    "budget_to_quota_rule",
    "filter_quota_rules",
    "flatten_entitlement_plan",
    "flatten_provider_plan",
]
