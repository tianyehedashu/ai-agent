"""
Gateway Background Jobs

- gateway_rollup_job: 5 分钟一次，把 GatewayRequestLog 增量聚合写入 gateway_metrics_hourly
- gateway_metrics_repair_loop: 每日一次，重算最近 N 小时 hourly（覆盖写）
- gateway_alert_job: 1 分钟一次，扫规则、写事件、发 webhook + 站内通知
- gateway_partition_job: 每天一次，确保下两个月的分区表存在，并清理过期配额汇总行
- gateway_request_log_retention_loop: 按配置间隔删除早于保留期的整月分区
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from domains.gateway.application.observability.gateway_alert_job import gateway_alert_loop
from domains.gateway.infrastructure.jobs.sql_jobs_repository import GatewaySqlJobsRepository
from domains.gateway.infrastructure.repositories.gateway_rollup_state_repository import (
    GatewayRollupStateRepository,
)
from domains.gateway.infrastructure.repositories.metrics_rollup_repository import (
    GatewayMetricsRollupRepository,
    RollupUpsertMode,
)
from domains.gateway.infrastructure.repositories.quota_plan_usage_bucket_repository import (
    QuotaPlanUsageBucketRepository,
)
from libs.background_tasks import register_app_background_task
from libs.db.database import get_background_session_context
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

_QUOTA_BUCKET_RETENTION_DAYS = 90


async def _cleanup_stale_quota_usage_buckets(session: AsyncSession) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=_QUOTA_BUCKET_RETENTION_DAYS)
    repo = QuotaPlanUsageBucketRepository(session)
    deleted = await repo.delete_stale_updated_before(cutoff)
    if deleted:
        await session.commit()
    return deleted


def _floor_hour(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


# =============================================================================
# Rollup
# =============================================================================


async def gateway_rollup_loop() -> None:
    """按 watermark 增量 rollup 至当前整点小时。"""
    interval = settings.gateway_rollup_interval_seconds
    while True:
        try:
            now = datetime.now(UTC)
            until = _floor_hour(now)
            async with get_background_session_context() as session:
                state_repo = GatewayRollupStateRepository(session)
                since = await state_repo.read_for_update()
                if since >= until:
                    await session.rollback()
                else:
                    repo = GatewayMetricsRollupRepository(session)
                    count = await repo.rollup_window(
                        since,
                        until,
                        mode=RollupUpsertMode.INCREMENT,
                    )
                    await state_repo.set_last_rolled_at(until)
                    await session.commit()
                    logger.debug(
                        "gateway_rollup_job: upserted %d rows [%s, %s)",
                        count,
                        since.isoformat(),
                        until.isoformat(),
                    )
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_rollup_job error: %s", exc)
        await asyncio.sleep(interval)


async def gateway_metrics_repair_loop() -> None:
    """每日重算最近 N 小时 hourly，修正迟到日志与采样偏差。"""
    interval = settings.gateway_metrics_repair_interval_seconds
    repair_hours = settings.gateway_metrics_repair_hours
    while True:
        try:
            if repair_hours > 0:
                now = datetime.now(UTC)
                until = _floor_hour(now)
                since = until - timedelta(hours=repair_hours)
                async with get_background_session_context() as session:
                    repo = GatewayMetricsRollupRepository(session)
                    count = await repo.rollup_window(
                        since,
                        until,
                        mode=RollupUpsertMode.REPLACE,
                    )
                    logger.info(
                        "gateway_metrics_repair: rebuilt %d hourly row(s) [%s, %s)",
                        count,
                        since.isoformat(),
                        until.isoformat(),
                    )
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_metrics_repair_loop error: %s", exc)
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
                deleted_buckets = await _cleanup_stale_quota_usage_buckets(session)
                if deleted_buckets:
                    logger.info(
                        "gateway_quota_bucket_retention: deleted %d stale row(s)",
                        deleted_buckets,
                    )
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



def schedule_gateway_jobs(app: Any) -> None:
    """启动后台任务并登记到 app.state"""
    register_app_background_task(app, asyncio.create_task(gateway_rollup_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_metrics_repair_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_partition_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_request_log_retention_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_alert_loop()))


__all__ = [
    "gateway_alert_loop",
    "gateway_metrics_repair_loop",
    "gateway_partition_loop",
    "gateway_request_log_retention_loop",
    "gateway_rollup_loop",
    "schedule_gateway_jobs",
]
