"""上下游套餐配额用量读路径：汇总表优先，日志窗口聚合兜底。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast
import uuid

from sqlalchemy import DateTime, and_, func, literal, select, tuple_, union_all
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
)
from domains.gateway.domain.quota_plan import (
    PROVIDER_NS,
    QuotaPlanNamespace,
    compute_window_start_datetime,
    normalize_reset_strategy,
)
from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (
    GatewayQuotaPlanUsageBucket,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class QuotaWindowLookup:
    """单条配额规则的窗口查询键。"""

    ns: QuotaPlanNamespace
    plan_id: uuid.UUID
    quota_id: uuid.UUID
    window_seconds: int
    reset_strategy: str
    plan_valid_from: datetime | None
    period_reset_anchor: PeriodResetAnchor = DEFAULT_PERIOD_RESET_ANCHOR


@dataclass(frozen=True)
class QuotaWindowKey:
    ns: QuotaPlanNamespace
    plan_id: uuid.UUID
    quota_id: uuid.UUID
    window_start: datetime


@dataclass(frozen=True)
class QuotaUsageTotals:
    cost_usd: Decimal
    tokens: int
    requests: int


@dataclass(frozen=True)
class _LogWindowKey:
    ns: QuotaPlanNamespace
    plan_id: uuid.UUID
    window_start: datetime


_ZERO_TOTALS = QuotaUsageTotals(Decimal("0"), 0, 0)


def resolve_quota_window_key(lookup: QuotaWindowLookup, *, now: datetime) -> QuotaWindowKey:
    window_start = compute_window_start_datetime(
        now,
        lookup.window_seconds,
        strategy=normalize_reset_strategy(lookup.reset_strategy),
        plan_valid_from=lookup.plan_valid_from,
        period_reset_anchor=lookup.period_reset_anchor,
    )
    return QuotaWindowKey(
        ns=lookup.ns,
        plan_id=lookup.plan_id,
        quota_id=lookup.quota_id,
        window_start=window_start,
    )


class QuotaPlanUsageReadService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def batch_usage_for_quota_windows(
        self,
        items: list[QuotaWindowLookup],
        *,
        now: datetime | None = None,
    ) -> dict[QuotaWindowKey, QuotaUsageTotals]:
        if not items:
            return {}

        when = now or datetime.now(UTC)
        keys: list[QuotaWindowKey] = []
        for item in items:
            keys.append(resolve_quota_window_key(item, now=when))

        bucket_rows = await self._load_buckets(keys)
        result: dict[QuotaWindowKey, QuotaUsageTotals] = {}
        missing_log_windows: dict[_LogWindowKey, list[QuotaWindowKey]] = {}

        for key in keys:
            row = bucket_rows.get(key)
            if row is not None:
                result[key] = QuotaUsageTotals(
                    cost_usd=Decimal(row.cost_usd or 0),
                    tokens=int(row.tokens or 0),
                    requests=int(row.requests or 0),
                )
                continue
            log_key = _LogWindowKey(ns=key.ns, plan_id=key.plan_id, window_start=key.window_start)
            missing_log_windows.setdefault(log_key, []).append(key)

        if missing_log_windows:
            log_totals = await self._aggregate_logs(list(missing_log_windows.keys()), until=when)
            for log_key, quota_keys in missing_log_windows.items():
                totals = log_totals.get(log_key, _ZERO_TOTALS)
                for key in quota_keys:
                    result[key] = totals

        return result

    async def _load_buckets(
        self, keys: list[QuotaWindowKey]
    ) -> dict[QuotaWindowKey, GatewayQuotaPlanUsageBucket]:
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
                [(k.ns, k.plan_id, k.quota_id, k.window_start) for k in unique_keys]
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        out: dict[QuotaWindowKey, GatewayQuotaPlanUsageBucket] = {}
        for row in rows:
            key = QuotaWindowKey(
                ns=cast("QuotaPlanNamespace", row.ns),
                plan_id=row.plan_id,
                quota_id=row.quota_id,
                window_start=row.window_start,
            )
            out[key] = row
        return out

    async def _aggregate_logs(
        self,
        windows: list[_LogWindowKey],
        *,
        until: datetime,
    ) -> dict[_LogWindowKey, QuotaUsageTotals]:
        if not windows:
            return {}
        unique_windows = list(dict.fromkeys(windows))
        out: dict[_LogWindowKey, QuotaUsageTotals] = {}

        provider_windows = [w for w in unique_windows if w.ns == PROVIDER_NS]
        entitlement_windows = [w for w in unique_windows if w.ns != PROVIDER_NS]

        if provider_windows:
            provider_totals = await self._aggregate_logs_batch(
                provider_windows,
                until=until,
                plan_col=GatewayRequestLog.provider_plan_id,
            )
            for window in provider_windows:
                out[window] = provider_totals.get(
                    (window.plan_id, window.window_start),
                    _ZERO_TOTALS,
                )

        if entitlement_windows:
            entitlement_totals = await self._aggregate_logs_batch(
                entitlement_windows,
                until=until,
                plan_col=GatewayRequestLog.entitlement_plan_id,
            )
            for window in entitlement_windows:
                out[window] = entitlement_totals.get(
                    (window.plan_id, window.window_start),
                    _ZERO_TOTALS,
                )

        return out

    async def _aggregate_logs_batch(
        self,
        windows: list[_LogWindowKey],
        *,
        until: datetime,
        plan_col: object,
    ) -> dict[tuple[uuid.UUID, datetime], QuotaUsageTotals]:
        if not windows:
            return {}

        subqueries = [
            select(
                literal(window.plan_id, type_=PG_UUID(as_uuid=True)).label("plan_id"),
                literal(window.window_start, type_=DateTime(timezone=True)).label("window_start"),
                func.count(GatewayRequestLog.id).label("requests"),
                func.coalesce(
                    func.sum(GatewayRequestLog.input_tokens + GatewayRequestLog.output_tokens),
                    0,
                ).label("tokens"),
                func.coalesce(func.sum(GatewayRequestLog.cost_usd), 0).label("cost_usd"),
            ).where(
                and_(
                    plan_col == window.plan_id,
                    GatewayRequestLog.status == "success",
                    GatewayRequestLog.created_at >= window.window_start,
                    GatewayRequestLog.created_at <= until,
                )
            )
            for window in windows
        ]
        stmt = subqueries[0] if len(subqueries) == 1 else union_all(*subqueries)
        rows = (await self._session.execute(stmt)).all()

        return {
            (row.plan_id, row.window_start): QuotaUsageTotals(
                cost_usd=Decimal(row.cost_usd or 0),
                tokens=int(row.tokens or 0),
                requests=int(row.requests or 0),
            )
            for row in rows
        }


__all__ = [
    "QuotaPlanUsageReadService",
    "QuotaUsageTotals",
    "QuotaWindowKey",
    "QuotaWindowLookup",
    "resolve_quota_window_key",
]
