"""转发前 preflight 被拒时的 request log 异步落库。"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.proxy_metadata_builder import ProxyMetadataBuilder
from domains.gateway.application.request_log_failure_classification import (
    ClassifiedRequestLogFailure,
    classify_request_log_failure,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
    RequestLogRepository,
)
from libs.db.database import get_session_context, prefer_background_pool
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.gateway.application.proxy_context import ProxyContext

logger = get_logger(__name__)


def schedule_preflight_failure_log(
    ctx: ProxyContext,
    exc: BaseException,
    *,
    model: str | None = None,
) -> None:
    """Fire-and-forget：preflight 失败写一条 request log，不阻塞 HTTP 响应。"""
    classified = classify_request_log_failure(exc)
    task = asyncio.create_task(
        _write_preflight_failure_log(ctx, classified, model=model),
        name=f"preflight_failure_log:{ctx.request_id}",
    )
    task.add_done_callback(_log_task_failure)


def _log_task_failure(task: asyncio.Task[None]) -> None:
    with suppress(asyncio.CancelledError):
        exc = task.exception()
        if exc is not None:
            logger.warning("Preflight failure log task failed: %s", exc)


async def _write_preflight_failure_log(
    ctx: ProxyContext,
    classified: ClassifiedRequestLogFailure,
    *,
    model: str | None,
) -> None:
    route_name = (model or ctx.budget_model or "").strip() or None
    with prefer_background_pool():
        try:
            async with get_session_context() as session:
                metadata = await ProxyMetadataBuilder(session).build(ctx)
                team_id = ctx.team_id
                user_id_raw = metadata.get("gateway_user_id")
                user_id = uuid.UUID(str(user_id_raw)) if user_id_raw else ctx.user_id
                vkey_id = ctx.vkey.vkey_id if ctx.vkey else None
                team_snapshot = metadata.get("gateway_team_snapshot")
                await RequestLogRepository(session).insert(
                    team_id=team_id,
                    user_id=user_id,
                    vkey_id=vkey_id,
                    team_snapshot=team_snapshot if isinstance(team_snapshot, dict) else None,
                    user_email_snapshot=metadata.get("gateway_user_email_snapshot"),
                    vkey_name_snapshot=metadata.get("gateway_vkey_name_snapshot"),
                    route_snapshot=None,
                    credential_id=None,
                    credential_name_snapshot=None,
                    entitlement_plan_id=_uuid_or_none(metadata.get("gateway_entitlement_plan_id")),
                    provider_plan_id=None,
                    deployment_gateway_model_id=None,
                    deployment_model_name=None,
                    capability=ctx.capability.value,
                    route_name=route_name,
                    real_model=None,
                    provider=metadata.get("gateway_provider"),
                    status=classified.status.value,
                    error_code=classified.error_code,
                    error_message=classified.error_message,
                    input_tokens=0,
                    output_tokens=0,
                    cached_tokens=0,
                    cache_creation_tokens=0,
                    cost_usd=Decimal("0"),
                    revenue_usd=Decimal("0"),
                    pricing_snapshot=None,
                    latency_ms=0,
                    ttfb_ms=None,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id=ctx.request_id,
                    prompt_hash=None,
                    prompt_redacted=None,
                    response_summary=None,
                    metadata_extra={"failure_phase": "preflight"},
                    client_type=metadata.get("gateway_client_type"),
                    client_ua=metadata.get("gateway_client_ua"),
                )
        except Exception as write_exc:  # pragma: no cover
            logger.warning("Failed to persist preflight failure log: %s", write_exc)


def _uuid_or_none(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


__all__ = ["schedule_preflight_failure_log"]
