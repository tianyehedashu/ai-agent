"""配额规则实时用量快照批量填充。

- Platform / Upstream / Downstream 展示读 → DB 汇总表 + 日志窗口聚合
- Redis 仅服务 pre_call 预扣与限流
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.budget_usage_reads import (
    BudgetWindowLookup,
    PlatformBudgetUsageReadService,
    resolve_budget_window_key,
)
from domains.gateway.application.management.quota_plan_usage_reads import (
    QuotaPlanUsageReadService,
    QuotaWindowLookup,
    resolve_quota_window_key,
)
from domains.gateway.application.management.quota_rule_read_model import (
    QuotaRuleReadModel,
    QuotaRuleUsage,
)
from domains.gateway.domain.period_reset_anchor import (
    period_reset_anchor_from_plan_quota,
    period_reset_anchor_from_row,
)
from domains.gateway.domain.quota_plan import ENTITLEMENT_NS, PROVIDER_NS


def _usage_with_reset_at(
    rule: QuotaRuleReadModel,
    *,
    current_usd: Decimal,
    current_tokens: int,
    current_requests: int,
    current_images: int = 0,
) -> QuotaRuleUsage:
    prior = rule.usage
    return QuotaRuleUsage(
        current_usd=current_usd,
        current_tokens=current_tokens,
        current_requests=current_requests,
        current_images=current_images,
        window_start=prior.window_start if prior is not None else None,
        reset_at=prior.reset_at if prior is not None else None,
        budget_reset_at=prior.budget_reset_at if prior is not None else None,
    )


async def enrich_quota_rules_with_usage(
    rules: list[QuotaRuleReadModel],
    *,
    session: AsyncSession,
) -> list[QuotaRuleReadModel]:
    """批量为规则列表注入实时用量，返回新的规则列表（不修改原对象）。"""
    if not rules:
        return []

    now = datetime.now(UTC)

    budget_lookups: list[tuple[int, BudgetWindowLookup]] = []
    plan_lookups: list[tuple[int, QuotaWindowLookup]] = []

    for idx, rule in enumerate(rules):
        if rule.key.layer == "platform":
            if rule.source_ref.budget_id is None:
                continue
            target_kind = rule.key.target_kind or "tenant"
            tenant_scope = (
                rule.key.team_id
                if target_kind == "user" and rule.key.credential_id is None
                else None
            )
            budget_lookups.append(
                (
                    idx,
                    BudgetWindowLookup(
                        budget_id=rule.source_ref.budget_id,
                        period=rule.key.period or "total",
                        target_kind=target_kind,
                        target_id=rule.key.target_id,
                        model_name=rule.key.model_name,
                        credential_id=rule.key.credential_id,
                        tenant_id=tenant_scope,
                        period_reset_anchor=period_reset_anchor_from_row(
                            timezone=rule.key.period_timezone,
                            time_minutes=rule.key.period_reset_minutes,
                            day_of_month=rule.key.period_reset_day,
                        ),
                    ),
                )
            )
            continue

        if rule.key.layer == "upstream":
            if rule.source_ref.quota_id is None:
                continue
            plan_id = rule.source_ref.quota_id
            quota_id = rule.source_ref.quota_id
        elif rule.key.layer == "downstream":
            if rule.source_ref.plan_id is None or rule.source_ref.quota_id is None:
                continue
            plan_id = rule.source_ref.plan_id
            quota_id = rule.source_ref.quota_id
        else:
            continue

        ns = PROVIDER_NS if rule.key.layer == "upstream" else ENTITLEMENT_NS
        plan_lookups.append(
            (
                idx,
                QuotaWindowLookup(
                    ns=ns,
                    plan_id=plan_id,
                    quota_id=quota_id,
                    window_seconds=rule.key.window_seconds or 0,
                    reset_strategy=rule.key.reset_strategy or "rolling",
                    plan_valid_from=rule.valid_from,
                    period_reset_anchor=period_reset_anchor_from_plan_quota(
                        reset_timezone=rule.key.period_timezone,
                        reset_time_minutes=rule.key.period_reset_minutes,
                        reset_day_of_month=rule.key.period_reset_day,
                    ),
                ),
            )
        )

    budget_usage: dict[int, QuotaRuleUsage] = {}
    if budget_lookups:
        read_service = PlatformBudgetUsageReadService(session)
        lookups = [lookup for _, lookup in budget_lookups]
        totals_by_key = await read_service.batch_usage_for_budget_windows(lookups, now=now)
        for idx, lookup in budget_lookups:
            key = resolve_budget_window_key(lookup, now=now)
            totals = totals_by_key.get(key)
            if totals is None:
                continue
            budget_usage[idx] = _usage_with_reset_at(
                rules[idx],
                current_usd=totals.cost_usd,
                current_tokens=totals.tokens,
                current_requests=totals.requests,
                current_images=totals.images,
            )

    plan_usage: dict[int, QuotaRuleUsage] = {}
    if plan_lookups:
        read_service = QuotaPlanUsageReadService(session)
        lookups = [lookup for _, lookup in plan_lookups]
        totals_by_key = await read_service.batch_usage_for_quota_windows(lookups, now=now)
        for idx, lookup in plan_lookups:
            key = resolve_quota_window_key(lookup, now=now)
            totals = totals_by_key.get(key)
            if totals is None:
                continue
            plan_usage[idx] = _usage_with_reset_at(
                rules[idx],
                current_usd=totals.cost_usd,
                current_tokens=totals.tokens,
                current_requests=totals.requests,
                current_images=totals.images,
            )

    result: list[QuotaRuleReadModel] = []
    for idx, rule in enumerate(rules):
        usage: QuotaRuleUsage | None = None

        if idx in budget_usage:
            usage = budget_usage[idx]
        elif idx in plan_usage:
            usage = plan_usage[idx]

        if usage is None and rule.usage is not None:
            usage = rule.usage

        result.append(
            QuotaRuleReadModel(
                key=rule.key,
                source_ref=rule.source_ref,
                limits=rule.limits,
                usage=usage,
                plan_label=rule.plan_label,
                is_active=rule.is_active,
                valid_from=rule.valid_from,
                valid_until=rule.valid_until,
            )
        )

    return result


__all__ = ["enrich_quota_rules_with_usage"]
