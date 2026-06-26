"""Platform 预算配额用量读路径：汇总桶 + 日志窗口合并（展示 SSOT）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, and_, func, literal, or_, select, tuple_, union_all
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from domains.gateway.application.management.quota_plan_usage_reads import QuotaUsageTotals
from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    compute_period_window_start,
)
from domains.gateway.domain.platform_budget_display import (
    PlatformBudgetLogScope,
    platform_log_fallback_supported,
)
from domains.gateway.domain.quota_plan import PLATFORM_NS
from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (
    GatewayQuotaPlanUsageBucket,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.repositories.usage_axis_sql import (
    usage_axis_user_visibility_disjuncts,
    usage_axis_workspace_member_visibility_disjuncts,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class BudgetWindowLookup:
    """单条 platform 预算规则的窗口查询键。"""

    budget_id: uuid.UUID
    period: str
    target_kind: str
    target_id: uuid.UUID | None
    model_name: str | None
    credential_id: uuid.UUID | None
    tenant_id: uuid.UUID | None
    period_reset_anchor: PeriodResetAnchor = DEFAULT_PERIOD_RESET_ANCHOR

    def log_scope(self) -> PlatformBudgetLogScope:
        return PlatformBudgetLogScope(
            target_kind=self.target_kind,
            target_id=self.target_id,
            model_name=self.model_name,
            credential_id=self.credential_id,
            tenant_id=self.tenant_id,
        )


@dataclass(frozen=True)
class BudgetWindowKey:
    budget_id: uuid.UUID
    window_start: datetime


_ZERO_TOTALS = QuotaUsageTotals(Decimal("0"), 0, 0, 0)


def merge_platform_display_totals(
    bucket: QuotaUsageTotals,
    logs: QuotaUsageTotals,
) -> QuotaUsageTotals:
    """展示读合并：各维度取较大值，避免 bucket 初建截断历史窗口用量。"""
    return QuotaUsageTotals(
        cost_usd=max(bucket.cost_usd, logs.cost_usd),
        tokens=max(bucket.tokens, logs.tokens),
        requests=max(bucket.requests, logs.requests),
        images=max(bucket.images, logs.images),
    )


def _is_explicit_zero_bucket(totals: QuotaUsageTotals) -> bool:
    """人工清零写入的全零桶：不再与日志 max 合并。"""
    return (
        totals.tokens == 0 and totals.requests == 0 and totals.cost_usd == 0 and totals.images == 0
    )


def resolve_budget_window_key(lookup: BudgetWindowLookup, *, now: datetime) -> BudgetWindowKey:
    window_start = compute_period_window_start(now, lookup.period, lookup.period_reset_anchor)
    return BudgetWindowKey(budget_id=lookup.budget_id, window_start=window_start)


def _log_dimension_clauses(scope: PlatformBudgetLogScope) -> list[object]:
    clauses: list[object] = []
    kind = scope.target_kind
    target_id = scope.target_id
    if kind == "tenant" and target_id is not None:
        clauses.append(GatewayRequestLog.tenant_id == target_id)
    elif kind == "user" and target_id is not None:
        if scope.tenant_id is not None:
            clauses.append(GatewayRequestLog.tenant_id == scope.tenant_id)
            platform_inbound, vkey_owned = usage_axis_workspace_member_visibility_disjuncts(
                scope.tenant_id,
                target_id,
            )
            clauses.append(or_(platform_inbound, vkey_owned))
        else:
            platform_inbound, vkey_attributed = usage_axis_user_visibility_disjuncts(target_id)
            clauses.append(or_(platform_inbound, vkey_attributed))
    elif kind == "key" and target_id is not None:
        clauses.append(GatewayRequestLog.vkey_id == target_id)
    if scope.model_name is not None:
        clauses.append(GatewayRequestLog.route_name == scope.model_name)
    if scope.credential_id is not None:
        clauses.append(GatewayRequestLog.credential_id == scope.credential_id)
    return clauses


class PlatformBudgetUsageReadService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def batch_usage_for_budget_windows(
        self,
        items: list[BudgetWindowLookup],
        *,
        now: datetime | None = None,
    ) -> dict[BudgetWindowKey, QuotaUsageTotals]:
        """汇总桶与日志窗口合并展示。

        - 可日志归因的维度：``max(bucket, logs)``，避免桶初建截断历史用量
        - 人工清零（桶全 0）：以桶为准，不再被日志拉回
        - ``system`` 等无日志归因维度：仅有桶时用桶，无桶记 0
        """
        if not items:
            return {}

        when = now or datetime.now(UTC)
        keys: list[tuple[BudgetWindowKey, BudgetWindowLookup]] = []
        for item in items:
            key = resolve_budget_window_key(item, now=when)
            keys.append((key, item))

        bucket_rows = await self._load_buckets([k for k, _ in keys])

        needs_logs: list[tuple[BudgetWindowKey, BudgetWindowLookup]] = []
        for key, lookup in keys:
            if not platform_log_fallback_supported(lookup.log_scope()):
                continue
            row = bucket_rows.get(
                (PLATFORM_NS, lookup.budget_id, lookup.budget_id, key.window_start)
            )
            if row is None:
                needs_logs.append((key, lookup))
                continue
            bucket_usage = QuotaUsageTotals(
                cost_usd=Decimal(row.cost_usd or 0),
                tokens=int(row.tokens or 0),
                requests=int(row.requests or 0),
                images=int(getattr(row, "images", 0) or 0),
            )
            if not _is_explicit_zero_bucket(bucket_usage):
                needs_logs.append((key, lookup))

        log_totals: dict[BudgetWindowKey, QuotaUsageTotals] = {}
        if needs_logs:
            log_totals = await self._aggregate_logs(needs_logs, until=when)

        result: dict[BudgetWindowKey, QuotaUsageTotals] = {}
        for key, lookup in keys:
            row = bucket_rows.get(
                (PLATFORM_NS, lookup.budget_id, lookup.budget_id, key.window_start)
            )
            bucket_usage = (
                QuotaUsageTotals(
                    cost_usd=Decimal(row.cost_usd or 0),
                    tokens=int(row.tokens or 0),
                    requests=int(row.requests or 0),
                    images=int(getattr(row, "images", 0) or 0),
                )
                if row is not None
                else _ZERO_TOTALS
            )
            if not platform_log_fallback_supported(lookup.log_scope()):
                result[key] = bucket_usage
                continue
            logs_usage = log_totals.get(key, _ZERO_TOTALS)
            if row is not None and _is_explicit_zero_bucket(bucket_usage):
                result[key] = bucket_usage
            elif row is not None:
                result[key] = merge_platform_display_totals(bucket_usage, logs_usage)
            else:
                result[key] = logs_usage

        return result

    async def _load_buckets(
        self,
        keys: list[BudgetWindowKey],
    ) -> dict[tuple[str, uuid.UUID, uuid.UUID, datetime], GatewayQuotaPlanUsageBucket]:
        if not keys:
            return {}
        unique_keys = list(dict.fromkeys(keys))
        stmt = select(GatewayQuotaPlanUsageBucket).where(
            tuple_(
                GatewayQuotaPlanUsageBucket.ns,
                GatewayQuotaPlanUsageBucket.plan_id,
                GatewayQuotaPlanUsageBucket.quota_id,
                GatewayQuotaPlanUsageBucket.window_start,
            ).in_([(PLATFORM_NS, k.budget_id, k.budget_id, k.window_start) for k in unique_keys])
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        out: dict[tuple[str, uuid.UUID, uuid.UUID, datetime], GatewayQuotaPlanUsageBucket] = {}
        for row in rows:
            out[(row.ns, row.plan_id, row.quota_id, row.window_start)] = row
        return out

    async def _aggregate_logs(
        self,
        items: list[tuple[BudgetWindowKey, BudgetWindowLookup]],
        *,
        until: datetime,
    ) -> dict[BudgetWindowKey, QuotaUsageTotals]:
        if not items:
            return {}
        unique_items = list(dict.fromkeys(items))
        subqueries = [
            select(
                literal(lookup.budget_id, type_=PG_UUID(as_uuid=True)).label("budget_id"),
                literal(key.window_start, type_=DateTime(timezone=True)).label("window_start"),
                func.count(GatewayRequestLog.id).label("requests"),
                func.coalesce(
                    func.sum(GatewayRequestLog.input_tokens + GatewayRequestLog.output_tokens),
                    0,
                ).label("tokens"),
                func.coalesce(func.sum(GatewayRequestLog.cost_usd), 0).label("cost_usd"),
                func.coalesce(func.sum(GatewayRequestLog.image_count), 0).label("images"),
            ).where(
                and_(
                    GatewayRequestLog.status == "success",
                    GatewayRequestLog.created_at >= key.window_start,
                    GatewayRequestLog.created_at <= until,
                    *_log_dimension_clauses(lookup.log_scope()),
                )
            )
            for key, lookup in unique_items
        ]
        stmt = subqueries[0] if len(subqueries) == 1 else union_all(*subqueries)
        rows = (await self._session.execute(stmt)).all()
        return {
            BudgetWindowKey(
                budget_id=row.budget_id, window_start=row.window_start
            ): QuotaUsageTotals(
                cost_usd=Decimal(row.cost_usd or 0),
                tokens=int(row.tokens or 0),
                requests=int(row.requests or 0),
                images=int(row.images or 0),
            )
            for row in rows
        }


__all__ = [
    "BudgetWindowKey",
    "BudgetWindowLookup",
    "PlatformBudgetUsageReadService",
    "merge_platform_display_totals",
    "resolve_budget_window_key",
]
