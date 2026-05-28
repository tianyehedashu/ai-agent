"""配额规则实时用量快照批量填充。

为 QuotaRuleReadModel 列表批量读取 Redis 实时用量：
- Platform 层 → BudgetService Redis 桶
- Upstream / Downstream 层 → QuotaPlanService snapshot
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.budget_service import (
    BudgetService,
    BudgetUsageCoord,
    redis_model_segment_for_budget,
)
from domains.gateway.application.quota_plan_service import QuotaPlanService
from domains.gateway.domain.quota_plan import (
    ENTITLEMENT_NS,
    PROVIDER_NS,
    PlanQuotaSpec,
)
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.gateway.application.management.quota_rule_read_model import (
        QuotaRuleReadModel,
        QuotaRuleUsage,
    )

logger = get_logger(__name__)


@dataclass(frozen=True)
class _PlanLookupKey:
    """用于按 (ns, plan_id) 分组 quota rules。"""

    ns: str
    plan_id: uuid.UUID


async def enrich_quota_rules_with_usage(
    rules: list[QuotaRuleReadModel],
) -> list[QuotaRuleReadModel]:
    """批量为规则列表注入实时用量，返回新的规则列表（不修改原对象）。"""
    if not rules:
        return []

    budget_service = BudgetService()
    quota_service = QuotaPlanService()

    # ------------------------------------------------------------------
    # 1. 收集 Platform 层 BudgetUsageCoord
    # ------------------------------------------------------------------
    platform_coords: list[tuple[int, BudgetUsageCoord]] = []
    for idx, rule in enumerate(rules):
        if rule.key.layer != "platform":
            continue
        target_id_str = str(rule.key.target_id) if rule.key.target_id else None
        coord = BudgetUsageCoord(
            target_kind=rule.key.target_kind or "tenant",
            target_id=target_id_str,
            period=rule.key.period or "total",
            model_segment=redis_model_segment_for_budget(rule.key.model_name),
        )
        platform_coords.append((idx, coord))

    platform_usage: dict[BudgetUsageCoord, tuple[Decimal, int, int]] = {}
    if platform_coords:
        unique_coords = list({c for _, c in platform_coords})
        platform_usage = await budget_service.read_budget_usage_batch(unique_coords)

    # ------------------------------------------------------------------
    # 2. 收集 Upstream / Downstream 层 PlanQuotaSpec（按 plan 分组）
    # ------------------------------------------------------------------
    plan_specs: dict[_PlanLookupKey, list[tuple[int, PlanQuotaSpec]]] = {}
    for idx, rule in enumerate(rules):
        if rule.key.layer == "platform":
            continue
        if rule.source_ref.plan_id is None or rule.source_ref.quota_id is None:
            continue

        ns = PROVIDER_NS if rule.key.layer == "upstream" else ENTITLEMENT_NS
        key = _PlanLookupKey(ns=ns, plan_id=rule.source_ref.plan_id)

        spec = PlanQuotaSpec(
            quota_id=rule.source_ref.quota_id,
            label=rule.key.quota_label or "default",
            window_seconds=rule.key.window_seconds or 0,
            limit_usd=rule.limits.limit_usd,
            limit_tokens=rule.limits.limit_tokens,
            limit_requests=rule.limits.limit_requests,
            reset_strategy=rule.key.reset_strategy or "rolling",
        )
        plan_specs.setdefault(key, []).append((idx, spec))

    # 批量查询 plan snapshot
    plan_snapshots: dict[tuple[str, uuid.UUID, uuid.UUID], tuple[Decimal, int, int]] = {}
    if plan_specs:
        now = datetime.now(UTC)
        for key, items in plan_specs.items():
            specs = [spec for _, spec in items]
            snaps = await quota_service.snapshot(key.ns, key.plan_id, specs, now=now)
            for (_, spec), snap in zip(items, snaps, strict=True):
                plan_snapshots[(key.ns, key.plan_id, spec.quota_id)] = (
                    snap.used_usd,
                    snap.used_tokens,
                    snap.used_requests,
                )

    # ------------------------------------------------------------------
    # 3. 构建新的规则列表（immutable update）
    # ------------------------------------------------------------------
    result: list[QuotaRuleReadModel] = []
    for idx, rule in enumerate(rules):
        usage: QuotaRuleUsage | None = None

        if rule.key.layer == "platform":
            # 匹配 platform 用量
            matched = [c for i, c in platform_coords if i == idx]
            if matched:
                used = platform_usage.get(matched[0], (Decimal("0"), 0, 0))
                usage = QuotaRuleUsage(
                    current_usd=used[0],
                    current_tokens=used[1],
                    current_requests=used[2],
                )
        else:
            # 匹配 upstream / downstream 用量
            if rule.source_ref.plan_id is not None and rule.source_ref.quota_id is not None:
                ns = PROVIDER_NS if rule.key.layer == "upstream" else ENTITLEMENT_NS
                snap_key = (ns, rule.source_ref.plan_id, rule.source_ref.quota_id)
                if snap_key in plan_snapshots:
                    used = plan_snapshots[snap_key]
                    usage = QuotaRuleUsage(
                        current_usd=used[0],
                        current_tokens=used[1],
                        current_requests=used[2],
                    )

        # 如果无法获取实时用量，回退到已有的 usage（Platform 层可能已有 DB 值）
        if usage is None and rule.usage is not None:
            usage = rule.usage

        from domains.gateway.application.management.quota_rule_read_model import (
            QuotaRuleReadModel,
        )

        result.append(
            QuotaRuleReadModel(
                key=rule.key,
                source_ref=rule.source_ref,
                limits=rule.limits,
                usage=usage,
                plan_label=rule.plan_label,
                is_active=rule.is_active,
            )
        )

    return result


__all__ = ["enrich_quota_rules_with_usage"]
