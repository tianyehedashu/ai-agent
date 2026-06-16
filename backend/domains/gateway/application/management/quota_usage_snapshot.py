"""配额规则实时用量快照批量填充。

- Platform 层 → BudgetService Redis 桶
- Upstream / Downstream 层 → DB 汇总表 + 日志窗口聚合（Redis 仅服务 pre_call 限流）
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.budget_service import (
    BudgetService,
    BudgetUsageCoord,
    redis_credential_segment_for_budget,
    redis_model_segment_for_budget,
    redis_tenant_segment_for_budget,
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
from domains.gateway.domain.quota_plan import ENTITLEMENT_NS, PROVIDER_NS


async def enrich_quota_rules_with_usage(
    rules: list[QuotaRuleReadModel],
    *,
    session: AsyncSession,
) -> list[QuotaRuleReadModel]:
    """批量为规则列表注入实时用量，返回新的规则列表（不修改原对象）。"""
    if not rules:
        return []

    budget_service = BudgetService()
    now = datetime.now(UTC)

    platform_coords: list[tuple[int, BudgetUsageCoord]] = []
    plan_lookups: list[tuple[int, QuotaWindowLookup]] = []

    for idx, rule in enumerate(rules):
        if rule.key.layer == "platform":
            target_id_str = str(rule.key.target_id) if rule.key.target_id else None
            target_kind = rule.key.target_kind or "tenant"
            tenant_seg = (
                redis_tenant_segment_for_budget(rule.key.team_id)
                if target_kind == "user" and rule.key.credential_id is None
                else None
            )
            coord = BudgetUsageCoord(
                target_kind=target_kind,
                target_id=target_id_str,
                period=rule.key.period or "total",
                model_segment=redis_model_segment_for_budget(rule.key.model_name),
                credential_segment=redis_credential_segment_for_budget(rule.key.credential_id),
                tenant_segment=tenant_seg,
            )
            platform_coords.append((idx, coord))
            continue

        if rule.source_ref.plan_id is None or rule.source_ref.quota_id is None:
            continue

        ns = PROVIDER_NS if rule.key.layer == "upstream" else ENTITLEMENT_NS
        plan_lookups.append(
            (
                idx,
                QuotaWindowLookup(
                    ns=ns,
                    plan_id=rule.source_ref.plan_id,
                    quota_id=rule.source_ref.quota_id,
                    window_seconds=rule.key.window_seconds or 0,
                    reset_strategy=rule.key.reset_strategy or "rolling",
                    plan_valid_from=rule.plan_valid_from,
                ),
            )
        )

    platform_usage: dict[BudgetUsageCoord, tuple[Decimal, int, int]] = {}
    if platform_coords:
        unique_coords = list({c for _, c in platform_coords})
        platform_usage = await budget_service.read_budget_usage_batch(unique_coords)

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
            plan_usage[idx] = QuotaRuleUsage(
                current_usd=totals.cost_usd,
                current_tokens=totals.tokens,
                current_requests=totals.requests,
            )

    result: list[QuotaRuleReadModel] = []
    for idx, rule in enumerate(rules):
        usage: QuotaRuleUsage | None = None

        if rule.key.layer == "platform":
            matched = [c for i, c in platform_coords if i == idx]
            if matched:
                used = platform_usage.get(matched[0], (Decimal("0"), 0, 0))
                usage = QuotaRuleUsage(
                    current_usd=used[0],
                    current_tokens=used[1],
                    current_requests=used[2],
                )
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
                plan_valid_from=rule.plan_valid_from,
            )
        )

    return result


__all__ = ["enrich_quota_rules_with_usage"]
