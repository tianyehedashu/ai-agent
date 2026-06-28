"""Gateway 告警后台任务（短事务 + commit 后 webhook）。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from bootstrap.config import settings
from domains.gateway.domain.alert.alert_evaluation import (
    AlertEvaluationResult,
    alert_cooldown_elapsed,
    evaluate_alert_rule,
)
from domains.gateway.domain.alert.alert_rule_snapshot import AlertRuleSnapshot
from domains.gateway.infrastructure.repositories.alert_repository import GatewayAlertRepository
from libs.db.database import get_background_session_context
from utils.logging import get_logger

logger = get_logger(__name__)


async def _send_webhook(url: str, payload: dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload)
    except Exception as exc:  # pragma: no cover
        logger.warning("alert webhook failed: %s", exc)


async def run_gateway_alert_cycle() -> None:
    """执行一轮告警扫描：单 read session 评估，单 write session 落库，commit 后外呼。"""
    now = datetime.now(UTC)
    pending_triggers: list[tuple[AlertRuleSnapshot, AlertEvaluationResult]] = []

    async with get_background_session_context() as read_session:
        repo = GatewayAlertRepository(read_session)
        rules = await repo.list_all_enabled_rules()
        for snapshot in rules:
            try:
                aggregates = await repo.fetch_rule_metric_aggregates(snapshot, now)
                result = evaluate_alert_rule(snapshot, aggregates)
                if result is None or not result.triggered:
                    continue
                if not alert_cooldown_elapsed(snapshot.last_triggered_at, now):
                    continue
                pending_triggers.append((snapshot, result))
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "gateway_alert_job rule %s eval error: %s",
                    snapshot.rule_id,
                    exc,
                )

    if not pending_triggers:
        return

    webhook_queue: list[tuple[str, dict[str, Any]]] = []
    async with get_background_session_context() as write_session:
        write_repo = GatewayAlertRepository(write_session)
        for snapshot, result in pending_triggers:
            try:
                payload = await write_repo.record_trigger(
                    snapshot,
                    value=result.value,
                    now=now,
                )
                channels = snapshot.channels or {}
                raw_url = channels.get("webhook")
                if isinstance(raw_url, str) and raw_url.strip() and payload is not None:
                    webhook_queue.append((raw_url.strip(), payload))
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "gateway_alert_job rule %s write error: %s",
                    snapshot.rule_id,
                    exc,
                )

    for url, payload in webhook_queue:
        await _send_webhook(url, payload)


async def gateway_alert_loop() -> None:
    """1 分钟一次，扫规则触发。"""
    interval = settings.gateway_alert_interval_seconds
    while True:
        try:
            await run_gateway_alert_cycle()
        except Exception as exc:  # pragma: no cover
            logger.warning("gateway_alert_job error: %s", exc)
        await asyncio.sleep(interval)


__all__ = ["gateway_alert_loop", "run_gateway_alert_cycle"]
