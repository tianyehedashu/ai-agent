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
from typing import Any

from bootstrap.config import settings
from domains.gateway.application.gateway_alert_job import gateway_alert_loop
from domains.gateway.infrastructure.jobs.sql_jobs_repository import GatewaySqlJobsRepository
from domains.gateway.infrastructure.repositories.metrics_rollup_repository import (
    GatewayMetricsRollupRepository,
)
from libs.background_tasks import register_app_background_task
from libs.db.database import get_background_session_context
from utils.logging import get_logger

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
            async with get_background_session_context() as session:
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
            async with get_background_session_context() as session:
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
                async with get_background_session_context() as session:
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
# Plan Lifecycle (上下游对称 ProviderPlan / EntitlementPlan)
# =============================================================================


async def gateway_plan_lifecycle_loop() -> None:
    """5 分钟一次，统一处理上下游 plan 过期 + auto_renew。"""
    interval = settings.gateway_rollup_interval_seconds
    while True:
        try:
            async with get_background_session_context() as session:
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
