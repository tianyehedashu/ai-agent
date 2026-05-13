"""
Gateway Background Jobs

- gateway_rollup_job: 5 分钟一次，把 GatewayRequestLog 聚合写入 gateway_metrics_hourly
- gateway_alert_job: 1 分钟一次，扫规则、写事件、发 webhook + 站内通知
- gateway_partition_job: 每天一次，确保下两个月的分区表存在
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, text

from bootstrap.config import settings
from domains.gateway.infrastructure.models.alert import (
    GatewayAlertEvent,
    GatewayAlertRule,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.repositories.metrics_rollup_repository import (
    GatewayMetricsRollupRepository,
)
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
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_rollup_job error: %s", exc)
        await asyncio.sleep(interval)


# =============================================================================
# Partition Maintenance
# =============================================================================


async def _ensure_partition(session: AsyncSession, year: int, month: int) -> None:
    start = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month + 1, 1, tzinfo=UTC)
    partition_name = f"gateway_request_logs_y{year:04d}m{month:02d}"
    await session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF gateway_request_logs
            FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
            """
        )
    )
    await session.commit()


async def gateway_partition_loop() -> None:
    """每天一次，确保下两个月分区存在"""
    interval = settings.gateway_partition_interval_seconds
    while True:
        try:
            async with get_session_context() as session:
                now = datetime.now(UTC)
                for delta in (0, 1, 2):
                    target = (now.replace(day=1) + timedelta(days=delta * 32)).replace(
                        day=1
                    )
                    await _ensure_partition(session, target.year, target.month)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_partition_job error: %s", exc)
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
            await session.execute(
                select(func.count()).select_from(base_q.subquery())
            )
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
            await session.execute(
                select(func.count()).select_from(base_q.subquery())
            )
        ).scalar_one()
        rate_per_min = float(cnt) / max(rule.window_minutes, 1)
        return rate_per_min > float(rule.threshold), rate_per_min
    if metric == "latency_p95":
        # 使用 PERCENTILE_CONT 近似 p95（PG 10+ 支持）
        sub = base_q.subquery()
        stmt = select(
            func.percentile_cont(0.95).within_group(sub.c.latency_ms.asc()).label("p95")
        )
        row = (await session.execute(stmt)).one()
        p95 = float(row.p95 or 0)
        return p95 > float(rule.threshold), p95
    if metric == "budget_usage":
        # budget_usage 需要参考 budget 表；简化为 cost_usd 总和
        sub = base_q.subquery()
        total = (
            await session.execute(select(func.sum(sub.c.cost_usd)))
        ).scalar_one() or 0
        total_f = float(total)
        return total_f > float(rule.threshold), total_f
    return None


async def _send_webhook(url: str, payload: dict[str, Any]) -> None:
    try:
        import httpx

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
                    await session.execute(
                        select(GatewayAlertRule).where(
                            GatewayAlertRule.enabled.is_(True)
                        )
                    )
                ).scalars().all()
                now = datetime.now(UTC)
                for rule in rules:
                    result = await _evaluate_rule(session, rule, now)
                    if result is None:
                        continue
                    triggered, value = result
                    if not triggered:
                        continue
                    # 静默期：5 分钟内不重复触发
                    if rule.last_triggered_at and (
                        now - rule.last_triggered_at
                    ).total_seconds() < 300:
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
                    # 通知
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
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_alert_job error: %s", exc)
        await asyncio.sleep(interval)


def schedule_gateway_jobs(app: Any) -> None:
    """启动后台任务并登记到 app.state"""
    from libs.background_tasks import register_app_background_task

    register_app_background_task(app, asyncio.create_task(gateway_rollup_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_partition_loop()))
    register_app_background_task(app, asyncio.create_task(gateway_alert_loop()))


__all__ = [
    "gateway_alert_loop",
    "gateway_partition_loop",
    "gateway_rollup_loop",
    "schedule_gateway_jobs",
]
