"""GatewayAlertRule / GatewayAlertEvent 仓储（多租户 + system 表）。"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from domains.gateway.domain.alert.alert_metric_aggregates import AlertMetricAggregates
from domains.gateway.domain.alert.alert_rule_snapshot import AlertRuleSnapshot
from domains.gateway.infrastructure.models.alert import GatewayAlertEvent, GatewayAlertRule
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayAlertRule
from libs.db.base_repository import TenantScopedRepositoryBase

if TYPE_CHECKING:
    from datetime import datetime
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class GatewayAlertRepository(TenantScopedRepositoryBase[GatewayAlertRule]):
    """租户告警规则；系统级规则见 ``list_system``。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._session = session

    @property
    def model_class(self) -> type[GatewayAlertRule]:
        return GatewayAlertRule

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[GatewayAlertRule]:
        stmt = (
            select(GatewayAlertRule)
            .where(GatewayAlertRule.tenant_id == tenant_id)
            .order_by(GatewayAlertRule.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_rules_for_tenant(self, tenant_id: uuid.UUID) -> list[GatewayAlertRule]:
        return await self.list_for_tenant(tenant_id)

    async def list_system(self, *, only_enabled: bool = False) -> list[SystemGatewayAlertRule]:
        clauses: list[object] = []
        if only_enabled:
            clauses.append(SystemGatewayAlertRule.enabled.is_(True))
        stmt = select(SystemGatewayAlertRule).where(*clauses).order_by(SystemGatewayAlertRule.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_events_for_tenant(
        self, tenant_id: uuid.UUID, *, limit: int
    ) -> list[GatewayAlertEvent]:
        stmt = (
            select(GatewayAlertEvent)
            .where(GatewayAlertEvent.tenant_id == tenant_id)
            .order_by(GatewayAlertEvent.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_rule(self, rule_id: uuid.UUID) -> GatewayAlertRule | None:
        return await self._session.get(GatewayAlertRule, rule_id)

    async def create_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        description: str | None,
        metric: str,
        threshold: Decimal,
        window_minutes: int,
        channels: dict[str, Any],
        enabled: bool,
    ) -> GatewayAlertRule:
        rule = GatewayAlertRule(
            tenant_id=tenant_id,
            name=name,
            description=description,
            metric=metric,
            threshold=threshold,
            window_minutes=window_minutes,
            channels=channels,
            enabled=enabled,
        )
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def update_rule_fields(
        self, rule: GatewayAlertRule, fields: dict[str, Any]
    ) -> GatewayAlertRule:
        for field, value in fields.items():
            setattr(rule, field, value)
        await self._session.flush()
        return rule

    async def delete_rule(self, rule: GatewayAlertRule) -> None:
        await self._session.delete(rule)
        await self._session.flush()

    async def list_all_enabled_rules(self) -> list[AlertRuleSnapshot]:
        """租户 + 系统级所有已启用规则（告警 job 用）。"""
        tenant_rows = (
            (
                await self._session.execute(
                    select(GatewayAlertRule).where(GatewayAlertRule.enabled.is_(True))
                )
            )
            .scalars()
            .all()
        )
        system_rows = await self.list_system(only_enabled=True)
        snapshots: list[AlertRuleSnapshot] = [
            AlertRuleSnapshot(
                rule_id=row.id,
                tenant_id=row.tenant_id,
                is_system=False,
                name=row.name,
                metric=row.metric,
                threshold=row.threshold,
                window_minutes=row.window_minutes,
                channels=dict(row.channels or {}),
                last_triggered_at=row.last_triggered_at,
            )
            for row in tenant_rows
        ]
        snapshots.extend(
            AlertRuleSnapshot(
                rule_id=row.id,
                tenant_id=None,
                is_system=True,
                name=row.name,
                metric=row.metric,
                threshold=row.threshold,
                window_minutes=row.window_minutes,
                channels=dict(row.channels or {}),
                last_triggered_at=row.last_triggered_at,
            )
            for row in system_rows
        )
        return snapshots

    async def fetch_rule_metric_aggregates(
        self,
        snapshot: AlertRuleSnapshot,
        now: datetime,
    ) -> AlertMetricAggregates:
        """按窗口聚合 request log，返回原始指标（评估在 domain）。"""
        window_start = now - timedelta(minutes=snapshot.window_minutes)
        base_q = select(GatewayRequestLog).where(
            GatewayRequestLog.created_at >= window_start,
            GatewayRequestLog.created_at <= now,
        )
        if snapshot.tenant_id is not None:
            base_q = base_q.where(GatewayRequestLog.tenant_id == snapshot.tenant_id)

        metric = snapshot.metric
        if metric == "error_rate":
            cnt_total = (
                await self._session.execute(select(func.count()).select_from(base_q.subquery()))
            ).scalar_one()
            cnt_err = (
                await self._session.execute(
                    select(func.count()).select_from(
                        base_q.where(GatewayRequestLog.status != "success").subquery()
                    )
                )
            ).scalar_one()
            return AlertMetricAggregates(
                metric=metric,
                total_count=int(cnt_total),
                error_count=int(cnt_err),
                window_minutes=snapshot.window_minutes,
            )
        if metric == "request_rate":
            cnt = (
                await self._session.execute(select(func.count()).select_from(base_q.subquery()))
            ).scalar_one()
            return AlertMetricAggregates(
                metric=metric,
                request_count=int(cnt),
                window_minutes=snapshot.window_minutes,
            )
        if metric == "latency_p95":
            sub = base_q.subquery()
            stmt = select(
                func.percentile_cont(0.95).within_group(sub.c.latency_ms.asc()).label("p95")
            )
            row = (await self._session.execute(stmt)).one()
            p95 = float(row.p95) if row.p95 is not None else None
            return AlertMetricAggregates(
                metric=metric,
                latency_p95_ms=p95,
                window_minutes=snapshot.window_minutes,
            )
        if metric == "budget_usage":
            sub = base_q.subquery()
            total = (
                await self._session.execute(select(func.sum(sub.c.cost_usd)))
            ).scalar_one() or 0
            return AlertMetricAggregates(
                metric=metric,
                cost_sum=float(total),
                window_minutes=snapshot.window_minutes,
            )
        return AlertMetricAggregates(metric=metric, window_minutes=snapshot.window_minutes)

    async def record_trigger(
        self,
        snapshot: AlertRuleSnapshot,
        *,
        value: float,
        now: datetime,
    ) -> dict[str, Any] | None:
        """写入事件、更新 last_triggered_at；返回 webhook payload（无 webhook 则仍返回 payload）。"""
        event = GatewayAlertEvent(
            rule_id=snapshot.rule_id,
            tenant_id=snapshot.tenant_id,
            metric_value=Decimal(str(value)),
            threshold=snapshot.threshold,
            severity="warning",
            payload={
                "window_minutes": snapshot.window_minutes,
                "metric": snapshot.metric,
            },
            notified=True,
        )
        self._session.add(event)
        if snapshot.is_system:
            system_rule = await self._session.get(SystemGatewayAlertRule, snapshot.rule_id)
            if system_rule is not None:
                system_rule.last_triggered_at = now
        else:
            tenant_rule = await self._session.get(GatewayAlertRule, snapshot.rule_id)
            if tenant_rule is not None:
                tenant_rule.last_triggered_at = now
        await self._session.flush()
        return {
            "rule": snapshot.name,
            "metric": snapshot.metric,
            "value": value,
            "threshold": float(snapshot.threshold),
            "team_id": str(snapshot.tenant_id) if snapshot.tenant_id else None,
            "at": now.isoformat(),
        }


__all__ = ["GatewayAlertRepository"]
