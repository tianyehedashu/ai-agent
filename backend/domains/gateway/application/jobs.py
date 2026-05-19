"""
Gateway Background Jobs

- gateway_rollup_job: 5 分钟一次，把 GatewayRequestLog 聚合写入 gateway_metrics_hourly
- gateway_alert_job: 1 分钟一次，扫规则、写事件、发 webhook + 站内通知
- gateway_partition_job: 每天一次，确保下两个月的分区表存在
- gateway_request_log_retention_loop: 按配置间隔删除早于保留期的整月分区
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import func, select

from bootstrap.config import settings
from domains.gateway.infrastructure.jobs.sql_jobs_repository import GatewaySqlJobsRepository
from domains.gateway.infrastructure.models.alert import (
    GatewayAlertEvent,
    GatewayAlertRule,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.repositories.metrics_rollup_repository import (
    GatewayMetricsRollupRepository,
)
from libs.background_tasks import register_app_background_task
from libs.db.database import get_session_context
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


# =============================================================================
# Rollup
# =============================================================================


async def gateway_rollup_loop() -> None:
    """5 分钟一次，rollup 最近 1 小时数据"""
    interval = settings.gateway_rollup_interval_seconds
    while True:
        try:
            now = datetime.now(UTC)
            until = now.replace(minute=0, second=0, microsecond=0)
            since = until - timedelta(hours=2)
            async with get_session_context() as session:
                repo = GatewayMetricsRollupRepository(session)
                count = await repo.rollup_window(since, until)
                logger.debug("gateway_rollup_job: upserted %d rows", count)
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_rollup_job error: %s", exc)
        await asyncio.sleep(interval)


# =============================================================================
# Partition Maintenance
# =============================================================================


async def gateway_partition_loop() -> None:
    """每天一次，确保下两个月分区存在"""
    interval = settings.gateway_partition_interval_seconds
    while True:
        try:
            async with get_session_context() as session:
                sql_jobs = GatewaySqlJobsRepository(session)
                now = datetime.now(UTC)
                for delta in (0, 1, 2):
                    target = (now.replace(day=1) + timedelta(days=delta * 32)).replace(day=1)
                    await sql_jobs.ensure_request_log_partition(target.year, target.month)
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_partition_job error: %s", exc)
        await asyncio.sleep(interval)


async def gateway_request_log_retention_loop() -> None:
    """按 ``gateway_request_log_retention_interval_seconds`` 清理过期明细分区。"""
    interval = settings.gateway_request_log_retention_interval_seconds
    while True:
        try:
            retention = settings.gateway_request_log_retention_days
            if retention is not None and retention > 0:
                async with get_session_context() as session:
                    sql_jobs = GatewaySqlJobsRepository(session)
                    dropped = await sql_jobs.drop_expired_request_log_partitions(retention)
                    if dropped:
                        logger.info(
                            "gateway_request_log_retention: dropped %d partition(s)",
                            dropped,
                        )
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_request_log_retention_loop error: %s", exc)
        await asyncio.sleep(interval)


# =============================================================================
# Alerts
# =============================================================================


async def _evaluate_rule(
    session: AsyncSession,
    rule: GatewayAlertRule,
    now: datetime,
) -> tuple[bool, float] | None:
    """评估规则；返回 (triggered, value) 或 None（数据不足）"""
    window_start = now - timedelta(minutes=rule.window_minutes)
    base_q = select(GatewayRequestLog).where(
        GatewayRequestLog.created_at >= window_start,
        GatewayRequestLog.created_at <= now,
    )
    if rule.team_id is not None:
        base_q = base_q.where(GatewayRequestLog.team_id == rule.team_id)

    metric = rule.metric
    if metric == "error_rate":
        cnt_total = (
            await session.execute(select(func.count()).select_from(base_q.subquery()))
        ).scalar_one()
        if cnt_total == 0:
            return None
        cnt_err = (
            await session.execute(
                select(func.count()).select_from(
                    base_q.where(GatewayRequestLog.status != "success").subquery()
                )
            )
        ).scalar_one()
        rate = float(cnt_err) / float(cnt_total)
        return rate > float(rule.threshold), rate
    if metric == "request_rate":
        cnt = (
            await session.execute(select(func.count()).select_from(base_q.subquery()))
        ).scalar_one()
        rate_per_min = float(cnt) / max(rule.window_minutes, 1)
        return rate_per_min > float(rule.threshold), rate_per_min
    if metric == "latency_p95":
        sub = base_q.subquery()
        stmt = select(func.percentile_cont(0.95).within_group(sub.c.latency_ms.asc()).label("p95"))
        row = (await session.execute(stmt)).one()
        p95 = float(row.p95 or 0)
        return p95 > float(rule.threshold), p95
    if metric == "budget_usage":
        sub = base_q.subquery()
        total = (await session.execute(select(func.sum(sub.c.cost_usd)))).scalar_one() or 0
        total_f = float(total)
        return total_f > float(rule.threshold), total_f
    return None


async def _send_webhook(url: str, payload: dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload)
    except Exception as exc:  # pragma: no cover
        logger.warning("alert webhook failed: %s", exc)


async def gateway_alert_loop() -> None:
    """1 分钟一次，扫规则触发"""
    interval = settings.gateway_alert_interval_seconds
    while True:
        try:
            async with get_session_context() as session:
                rules = (
                    (
                        await session.execute(
                            select(GatewayAlertRule).where(GatewayAlertRule.enabled.is_(True))
                        )
                    )
                    .scalars()
                    .all()
                )
                now = datetime.now(UTC)
                for rule in rules:
                    result = await _evaluate_rule(session, rule, now)
                    if result is None:
                        continue
                    triggered, value = result
                    if not triggered:
                        continue
                    if (
                        rule.last_triggered_at
                        and (now - rule.last_triggered_at).total_seconds() < 300
                    ):
                        continue
                    event = GatewayAlertEvent(
                        rule_id=rule.id,
                        team_id=rule.team_id,
                        metric_value=Decimal(str(value)),
                        threshold=rule.threshold,
                        severity="warning",
                        payload={"window_minutes": rule.window_minutes, "metric": rule.metric},
                        notified=False,
                    )
                    session.add(event)
                    rule.last_triggered_at = now
                    await session.flush()
                    payload = {
                        "rule": rule.name,
                        "metric": rule.metric,
                        "value": value,
                        "threshold": float(rule.threshold),
                        "team_id": str(rule.team_id) if rule.team_id else None,
                        "at": now.isoformat(),
                    }
                    channels = rule.channels or {}
                    if channels.get("webhook"):
                        await _send_webhook(channels["webhook"], payload)
                    event.notified = True
                await session.commit()
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_alert_job error: %s", exc)
        await asyncio.sleep(interval)


# =============================================================================
# Plan Lifecycle (上下游对称 ProviderPlan / EntitlementPlan)
# =============================================================================


async def gateway_plan_lifecycle_loop() -> None:
    """5 分钟一次，统一处理上下游 plan 过期 + auto_renew。"""
    interval = settings.gateway_rollup_interval_seconds
    while True:
        try:
            async with get_session_context() as session:
                sql_jobs = GatewaySqlJobsRepository(session)
                e_off, e_on = await sql_jobs.process_plan_lifecycle_for_table(
                    table="entitlement_plans",
                    quota_table="entitlement_plan_quotas",
                )
                p_off, p_on = await sql_jobs.process_plan_lifecycle_for_table(
                    table="provider_plans",
                    quota_table="provider_plan_quotas",
                )
                await session.commit()
                if e_off or e_on or p_off or p_on:
                    logger.info(
                        "gateway_plan_lifecycle: entitlement off=%d renew=%d, provider off=%d renew=%d",
                        e_off,
                        e_on,
                        p_off,
                        p_on,
                    )
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_plan_lifecycle error: %s", exc)
        await asyncio.sleep(interval)


def schedule_gateway_jobs(app: Any) -> None:
    """启动后台任务并登记到 app.state"""
    register_app_background_task(app, asyncio.create_task(gateway_rollup_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_partition_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_request_log_retention_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_alert_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_plan_lifecycle_loop()))


__all__ = [
    "gateway_alert_loop",
    "gateway_partition_loop",
    "gateway_plan_lifecycle_loop",
    "gateway_request_log_retention_loop",
    "gateway_rollup_loop",
    "schedule_gateway_jobs",
]
