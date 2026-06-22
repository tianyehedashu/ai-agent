"""兼容层用量只读查询（供 identity 路由等调用，不暴露 ORM）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.domain.margin_read_model import (
    MarginGroupBy,
    margin_group_column_label,
    resolve_margin_group_label,
)
from domains.gateway.domain.usage_read_model import (
    UsageStatisticsBreakdownBy,
    UsageStatisticsGroupBy,
)
from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    EntitlementPlanRepository,
)
from domains.tenancy.application.team_service import TeamService


@dataclass(frozen=True)
class UserQuotaReadModel:
    """用户维度配额快照（兼容旧 /usage/quota 字段）。"""

    user_id: UUID
    daily_text_requests: int | None
    monthly_token_limit: int | None
    current_daily_text: int
    current_monthly_tokens: int
    daily_reset_at: datetime | None
    monthly_reset_at: datetime | None


@dataclass(frozen=True)
class UsageLogReadModel:
    """单条用量日志只读视图。"""

    id: UUID
    capability: str
    provider: str
    model: str | None
    key_source: str
    input_tokens: int | None
    output_tokens: int | None
    image_count: int | None
    cost_estimate: Decimal | None
    created_at: datetime


@dataclass(frozen=True)
class UsageStatisticsMetric:
    """调用统计指标，用于总计与分组行。"""

    requests: int
    success_count: int
    failure_count: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cache_creation_tokens: int
    cost_usd: Decimal
    avg_latency_ms: float
    avg_ttfb_ms: float
    cache_hit_count: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def success_rate(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.success_count / self.requests

    @property
    def cache_hit_rate(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.cache_hit_count / self.requests


@dataclass(frozen=True)
class UsageStatisticsItem(UsageStatisticsMetric):
    """调用统计分组行。"""

    group_key: str
    label: str
    group_key_parts: list[str] | None = None
    label_parts: list[str] | None = None


@dataclass(frozen=True)
class UsageStatisticsSummary:
    """调用统计响应读模型。"""

    start: datetime
    end: datetime
    group_by: UsageStatisticsGroupBy
    totals: UsageStatisticsMetric
    items: list[UsageStatisticsItem] = field(default_factory=list)


@dataclass(frozen=True)
class UsageStatisticsBreakdownSlice:
    group_key: str
    label: str
    requests: int
    share: float


@dataclass(frozen=True)
class UsageStatisticsBreakdownSummary:
    parent_group_by: UsageStatisticsGroupBy
    parent_group_key: str
    breakdown_by: UsageStatisticsBreakdownBy
    parent_requests: int
    items: list[UsageStatisticsBreakdownSlice] = field(default_factory=list)


@dataclass(frozen=True)
class UsageStatisticsBreakdownBatchSummary:
    """一次返回本页多个父行的二次分组分布。"""

    parent_group_by: UsageStatisticsGroupBy
    breakdown_by: UsageStatisticsBreakdownBy
    items: list[UsageStatisticsBreakdownSummary] = field(default_factory=list)


class GatewayUsageReadService:
    """从 Gateway 表读取用量与配额；调用方不 import ORM。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_quota_snapshot(self, user_id: UUID) -> UserQuotaReadModel | None:
        daily = (
            await self._session.execute(
                select(GatewayBudget).where(
                    GatewayBudget.scope == "user",
                    GatewayBudget.scope_id == user_id,
                    GatewayBudget.period == "daily",
                )
            )
        ).scalar_one_or_none()
        monthly = (
            await self._session.execute(
                select(GatewayBudget).where(
                    GatewayBudget.scope == "user",
                    GatewayBudget.scope_id == user_id,
                    GatewayBudget.period == "monthly",
                )
            )
        ).scalar_one_or_none()

        if daily is None and monthly is None:
            return None

        return UserQuotaReadModel(
            user_id=user_id,
            daily_text_requests=daily.limit_requests if daily else None,
            monthly_token_limit=monthly.limit_tokens if monthly else None,
            current_daily_text=daily.current_requests if daily else 0,
            current_monthly_tokens=monthly.current_tokens if monthly else 0,
            daily_reset_at=daily.reset_at if daily else None,
            monthly_reset_at=monthly.reset_at if monthly else None,
        )

    async def list_recent_usage_logs_for_user(
        self,
        user_id: UUID,
        *,
        limit: int,
        offset: int,
        window_days: int = 90,
    ) -> list[UsageLogReadModel]:
        since = datetime.now(UTC) - timedelta(days=window_days)
        member_teams = await TeamService(self._session).list_user_teams(user_id)
        team_ids = [t.id for t in member_teams]
        scope_filter = (
            or_(
                GatewayRequestLog.user_id == user_id,
                GatewayRequestLog.tenant_id.in_(team_ids),
            )
            if team_ids
            else GatewayRequestLog.user_id == user_id
        )
        stmt = (
            select(GatewayRequestLog)
            .where(scope_filter)
            .where(GatewayRequestLog.created_at >= since)
            .order_by(GatewayRequestLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        logs = list(result.scalars().all())
        return [
            UsageLogReadModel(
                id=log.id,
                capability=log.capability,
                provider=log.provider or "unknown",
                model=log.real_model,
                key_source="vkey" if log.vkey_id else "system",
                input_tokens=log.input_tokens,
                output_tokens=log.output_tokens,
                image_count=None,
                cost_estimate=log.cost_usd,
                created_at=log.created_at,
            )
            for log in logs
        ]


@dataclass(frozen=True)
class EntitlementUsageReadModel:
    """下游客户套餐用量摘要（来自 ``gateway_request_logs``）。"""

    plan_id: UUID
    requests: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cache_creation_tokens: int
    cost_usd: Decimal
    charged_usd: Decimal
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True)
class ProviderPlanCostReadModel:
    """上游厂商套餐成本摘要（来自 ``gateway_request_logs``）。"""

    plan_id: UUID
    requests: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cache_creation_tokens: int
    cost_usd: Decimal
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True)
class MarginGroupItem:
    group_key: str
    label: str
    revenue_usd: Decimal
    cost_usd: Decimal

    @property
    def margin_usd(self) -> Decimal:
        return self.revenue_usd - self.cost_usd

    @property
    def margin_ratio(self) -> float:
        if self.revenue_usd == 0:
            return 0.0
        return float(self.margin_usd / self.revenue_usd)


@dataclass(frozen=True)
class MarginSummaryReadModel:
    period_start: datetime
    period_end: datetime
    total_revenue_usd: Decimal
    total_cost_usd: Decimal
    group_by: MarginGroupBy = "credential"
    items: list[MarginGroupItem] = field(default_factory=list)

    @property
    def total_margin_usd(self) -> Decimal:
        return self.total_revenue_usd - self.total_cost_usd

    @property
    def group_column_label(self) -> str:
        return margin_group_column_label(self.group_by)


def _entitlement_revenue_decimal(
    *,
    requests: int,
    tokens: int,
    cost_usd: Decimal,
    unit_price_per_token: Decimal | None,
    unit_price_per_request: Decimal | None,
) -> Decimal:
    if unit_price_per_token is None and unit_price_per_request is None:
        # 缺省策略：客户单价未配置时按上游 cost 等价记账
        return cost_usd
    revenue = Decimal("0")
    if unit_price_per_token is not None:
        revenue += unit_price_per_token * Decimal(tokens)
    if unit_price_per_request is not None:
        revenue += unit_price_per_request * Decimal(requests)
    return revenue


class GatewayPlanUsageReadService:
    """上下游套餐统计读侧（CQRS read 工程分包）。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_entitlement_usage(
        self,
        plan_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> EntitlementUsageReadModel:
        end = until or datetime.now(UTC)
        start = since or (end - timedelta(days=30))
        stmt = select(
            func.count(GatewayRequestLog.id).label("requests"),
            func.coalesce(func.sum(GatewayRequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(GatewayRequestLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(GatewayRequestLog.cached_tokens), 0).label("cached_tokens"),
            func.coalesce(func.sum(GatewayRequestLog.cache_creation_tokens), 0).label(
                "cache_creation_tokens"
            ),
            func.coalesce(func.sum(GatewayRequestLog.cost_usd), 0).label("cost_usd"),
        ).where(
            and_(
                GatewayRequestLog.entitlement_plan_id == plan_id,
                GatewayRequestLog.created_at >= start,
                GatewayRequestLog.created_at <= end,
            )
        )
        row = (await self._session.execute(stmt)).one()
        requests = int(row.requests or 0)
        input_tokens = int(row.input_tokens or 0)
        output_tokens = int(row.output_tokens or 0)
        cached_tokens = int(row.cached_tokens or 0)
        cache_creation_tokens = int(row.cache_creation_tokens or 0)
        cost_usd = Decimal(row.cost_usd or 0)

        repo = EntitlementPlanRepository(self._session)
        quotas = await repo.list_quotas(plan_id)
        unit_t: Decimal | None = None
        unit_r: Decimal | None = None
        for q in quotas:
            if q.unit_price_usd_per_token is not None and unit_t is None:
                unit_t = q.unit_price_usd_per_token
            if q.unit_price_usd_per_request is not None and unit_r is None:
                unit_r = q.unit_price_usd_per_request
        charged = _entitlement_revenue_decimal(
            requests=requests,
            tokens=input_tokens + output_tokens,
            cost_usd=cost_usd,
            unit_price_per_token=unit_t,
            unit_price_per_request=unit_r,
        )

        return EntitlementUsageReadModel(
            plan_id=plan_id,
            requests=requests,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cost_usd=cost_usd,
            charged_usd=charged,
            period_start=start,
            period_end=end,
        )

    async def get_provider_plan_cost(
        self,
        plan_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> ProviderPlanCostReadModel:
        end = until or datetime.now(UTC)
        start = since or (end - timedelta(days=30))
        stmt = select(
            func.count(GatewayRequestLog.id).label("requests"),
            func.coalesce(func.sum(GatewayRequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(GatewayRequestLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(GatewayRequestLog.cached_tokens), 0).label("cached_tokens"),
            func.coalesce(func.sum(GatewayRequestLog.cache_creation_tokens), 0).label(
                "cache_creation_tokens"
            ),
            func.coalesce(func.sum(GatewayRequestLog.cost_usd), 0).label("cost_usd"),
        ).where(
            and_(
                GatewayRequestLog.provider_plan_id == plan_id,
                GatewayRequestLog.created_at >= start,
                GatewayRequestLog.created_at <= end,
            )
        )
        row = (await self._session.execute(stmt)).one()
        return ProviderPlanCostReadModel(
            plan_id=plan_id,
            requests=int(row.requests or 0),
            input_tokens=int(row.input_tokens or 0),
            output_tokens=int(row.output_tokens or 0),
            cached_tokens=int(row.cached_tokens or 0),
            cache_creation_tokens=int(row.cache_creation_tokens or 0),
            cost_usd=Decimal(row.cost_usd or 0),
            period_start=start,
            period_end=end,
        )

    async def get_team_margin_summary(
        self,
        team_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        group_by: MarginGroupBy = "credential",
    ) -> MarginSummaryReadModel:
        end = until or datetime.now(UTC)
        start = since or (end - timedelta(days=30))
        # 分组键
        group_col = {
            "credential": GatewayRequestLog.credential_id,
            "model": GatewayRequestLog.real_model,
            "team": GatewayRequestLog.tenant_id,
        }[group_by]

        if group_by == "credential":
            stmt = (
                select(
                    group_col.label("group_key"),
                    func.coalesce(func.sum(GatewayRequestLog.cost_usd), 0).label("cost_usd"),
                    func.max(GatewayRequestLog.credential_name_snapshot).label(
                        "credential_name_snapshot"
                    ),
                )
                .where(
                    and_(
                        GatewayRequestLog.tenant_id == team_id,
                        GatewayRequestLog.created_at >= start,
                        GatewayRequestLog.created_at <= end,
                    )
                )
                .group_by(group_col)
            )
        else:
            stmt = (
                select(
                    group_col.label("group_key"),
                    func.coalesce(func.sum(GatewayRequestLog.cost_usd), 0).label("cost_usd"),
                )
                .where(
                    and_(
                        GatewayRequestLog.tenant_id == team_id,
                        GatewayRequestLog.created_at >= start,
                        GatewayRequestLog.created_at <= end,
                    )
                )
                .group_by(group_col)
            )
        rows = (await self._session.execute(stmt)).all()

        credential_names: dict[UUID, str] = {}
        if group_by == "credential":
            cred_ids = [row.group_key for row in rows if row.group_key is not None]
            if cred_ids:
                creds = await ProviderCredentialRepository(self._session).list_by_ids(cred_ids)
                credential_names = {c.id: c.name for c in creds}

        team_names: dict[UUID, str] = {}
        if group_by == "team":
            grouped_team_ids = [row.group_key for row in rows if row.group_key is not None]
            if grouped_team_ids:
                team_names = await TeamService(self._session).get_display_names_by_ids(
                    grouped_team_ids
                )

        items: list[MarginGroupItem] = []
        total_cost = Decimal("0")
        total_revenue = Decimal("0")
        for row in rows:
            cost = Decimal(row.cost_usd or 0)
            # 默认 revenue = cost；后续可叠加按 entitlement_plan unit_price 计算的精确值
            revenue = cost
            cred_snap = row.credential_name_snapshot if group_by == "credential" else None
            group_key_str, label = resolve_margin_group_label(
                group_by,
                row.group_key,
                credential_names=credential_names,
                credential_name_snapshot=cred_snap,
                team_names=team_names,
            )
            items.append(
                MarginGroupItem(
                    group_key=group_key_str,
                    label=label,
                    revenue_usd=revenue,
                    cost_usd=cost,
                )
            )
            total_cost += cost
            total_revenue += revenue

        items.sort(key=lambda i: i.cost_usd, reverse=True)

        return MarginSummaryReadModel(
            period_start=start,
            period_end=end,
            total_revenue_usd=total_revenue,
            total_cost_usd=total_cost,
            group_by=group_by,
            items=items,
        )


__all__ = [
    "EntitlementUsageReadModel",
    "GatewayPlanUsageReadService",
    "GatewayUsageReadService",
    "MarginGroupBy",
    "MarginGroupItem",
    "MarginSummaryReadModel",
    "ProviderPlanCostReadModel",
    "UsageLogReadModel",
    "UsageStatisticsBreakdownBatchSummary",
    "UsageStatisticsBreakdownSlice",
    "UsageStatisticsBreakdownSummary",
    "UsageStatisticsItem",
    "UsageStatisticsMetric",
    "UsageStatisticsSummary",
    "UserQuotaReadModel",
]
