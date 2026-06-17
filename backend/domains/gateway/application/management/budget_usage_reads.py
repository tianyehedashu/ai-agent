"""Platform 预算配额用量读路径：汇总表 + 日志窗口合并（展示 SSOT）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, and_, func, literal, select, tuple_, union_all
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from domains.gateway.application.management.quota_plan_usage_reads import QuotaUsageTotals
from domains.gateway.domain.platform_budget_display import (
    PlatformBudgetLogScope,
    platform_log_fallback_supported,
)
from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    compute_period_window_start,
)
from domains.gateway.domain.quota_plan import PLATFORM_NS
from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (
    GatewayQuotaPlanUsageBucket,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog

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


_ZERO_TOTALS = QuotaUsageTotals(Decimal("0"), 0, 0)


def merge_platform_display_totals(
    bucket: QuotaUsageTotals,
    logs: QuotaUsageTotals,
) -> QuotaUsageTotals:
    """展示读合并：各维度取较大值，避免 bucket 初建截断历史窗口用量。"""
    return QuotaUsageTotals(
        cost_usd=max(bucket.cost_usd, logs.cost_usd),
        tokens=max(bucket.tokens, logs.tokens),
        requests=max(bucket.requests, logs.requests),
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
        clauses.append(GatewayRequestLog.user_id == target_id)
        if scope.tenant_id is not None:
            clauses.append(GatewayRequestLog.tenant_id == scope.tenant_id)
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
        if not items:
            return {}

        when = now or datetime.now(UTC)
        keys: list[tuple[BudgetWindowKey, BudgetWindowLookup]] = []
        for item in items:
            key = resolve_budget_window_key(item, now=when)
            keys.append((key, item))

        bucket_rows = await self._load_buckets([k for k, _ in keys])

        log_fallback_items = [
            (key, lookup) for key, lookup in keys if platform_log_fallback_supported(lookup.log_scope())
        ]
        log_totals: dict[BudgetWindowKey, QuotaUsageTotals] = {}
        if log_fallback_items:
            log_totals = await self._aggregate_logs(log_fallback_items, until=when)

        result: dict[BudgetWindowKey, QuotaUsageTotals] = {}
        for key, lookup in keys:
            bucket_key = (
                PLATFORM_NS,
                lookup.budget_id,
                lookup.budget_id,
                key.window_start,
            )
            row = bucket_rows.get(bucket_key)
            bucket_usage = (
                QuotaUsageTotals(
                    cost_usd=Decimal(row.cost_usd or 0),
                    tokens=int(row.tokens or 0),
                    requests=int(row.requests or 0),
                )
                if row is not None
                else _ZERO_TOTALS
            )
            if platform_log_fallback_supported(lookup.log_scope()):
                logs_usage = log_totals.get(key, _ZERO_TOTALS)
                result[key] = merge_platform_display_totals(bucket_usage, logs_usage)
            else:
                result[key] = bucket_usage

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
            ).in_(
                [
                    (PLATFORM_NS, k.budget_id, k.budget_id, k.window_start)
                    for k in unique_keys
                ]
            )
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
            BudgetWindowKey(budget_id=row.budget_id, window_start=row.window_start): QuotaUsageTotals(
                cost_usd=Decimal(row.cost_usd or 0),
                tokens=int(row.tokens or 0),
                requests=int(row.requests or 0),
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
