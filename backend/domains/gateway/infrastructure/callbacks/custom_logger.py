"""
GatewayCustomLogger - LiteLLM CustomLogger 实现

记录所有 Gateway 调用：
- 成功（含流式末帧）
- 失败
- 缓存命中
- Fallback 链路

每条记录写入：
- gateway_request_logs（按月分区）
- Redis 实时计数（用于 dashboard 与 budget）
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal
import time
from typing import Any
import uuid

from libs.db.database import get_session_context
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)


# Redis key 模板
REDIS_PREFIX = "gateway:metrics"


def _redis_keys(team_id: str | None, vkey_id: str | None, user_id: str | None) -> list[str]:
    """构建实时计数的 redis key 列表（多维度）"""
    keys: list[str] = []
    if team_id:
        keys.append(f"{REDIS_PREFIX}:team:{team_id}")
    if vkey_id:
        keys.append(f"{REDIS_PREFIX}:vkey:{vkey_id}")
    if user_id:
        keys.append(f"{REDIS_PREFIX}:user:{user_id}")
    return keys


def _import_custom_logger() -> Any:
    from litellm.integrations.custom_logger import CustomLogger

    return CustomLogger


_logger_instance: Any | None = None


def get_logger_singleton() -> Any:
    """获取全局 GatewayCustomLogger 单例（懒加载）"""
    global _logger_instance  # pylint: disable=global-statement
    if _logger_instance is None:
        _logger_instance = _build_logger_instance()
    return _logger_instance


class GatewayCustomLogger:
    """工厂入口（与 GatewayPiiGuardrail 一致，避免 import-time 加载 litellm）"""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return _build_logger_instance(*args, **kwargs)


def _build_logger_instance() -> Any:
    base_cls = _import_custom_logger()

    class _Impl(base_cls):  # type: ignore[misc, valid-type]
        async def async_log_success_event(
            self,
            kwargs: dict[str, Any],
            response_obj: Any,
            start_time: Any,
            end_time: Any,
        ) -> None:
            await _persist_event(
                kwargs=kwargs,
                response_obj=response_obj,
                start_time=start_time,
                end_time=end_time,
                status="success",
                error_code=None,
                error_message=None,
            )

        async def async_log_failure_event(
            self,
            kwargs: dict[str, Any],
            response_obj: Any,
            start_time: Any,
            end_time: Any,
        ) -> None:
            error = kwargs.get("exception") or kwargs.get("error") or response_obj
            error_code = type(error).__name__ if error else "UnknownError"
            error_message = str(error) if error else None
            await _persist_event(
                kwargs=kwargs,
                response_obj=response_obj,
                start_time=start_time,
                end_time=end_time,
                status="failed",
                error_code=error_code,
                error_message=error_message,
            )

        async def async_post_call_streaming_hook(
            self,
            user_api_key_dict: Any,
            response: Any,
        ) -> None:
            """流式末帧：通过 success_event 兜底，这里仅记录 ttfb"""
            return None

    return _Impl()


# =============================================================================
# Persist
# =============================================================================


def _safe_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC)
    return None


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    with suppress(ValueError, TypeError):
        return uuid.UUID(str(value))
    return None


def _calc_cost(kwargs: dict[str, Any], response_obj: Any) -> Decimal:
    """优先使用 LiteLLM 的 completion_cost；失败回退 0"""
    try:
        from litellm import completion_cost

        cost = completion_cost(
            completion_response=response_obj,
            model=kwargs.get("model"),
        )
        return Decimal(str(cost or 0))
    except Exception:  # pragma: no cover
        return Decimal("0")


def _extract_usage(response_obj: Any) -> tuple[int, int, int]:
    """提取 (input, output, cached) tokens"""
    if response_obj is None:
        return 0, 0, 0
    usage = getattr(response_obj, "usage", None) or {}

    def _usage_get(key: str, default: Any = None) -> Any:
        if isinstance(usage, dict):
            return usage.get(key, default)
        return getattr(usage, key, default)

    input_tokens = int(_usage_get("prompt_tokens", 0) or 0)
    output_tokens = int(_usage_get("completion_tokens", 0) or 0)
    cached_tokens = 0
    cache_details = _usage_get("prompt_tokens_details", None)
    if isinstance(cache_details, dict):
        cached_tokens = int(cache_details.get("cached_tokens", 0) or 0)
    return input_tokens, output_tokens, cached_tokens


def _summarize_response(response_obj: Any) -> dict[str, Any] | None:
    """提取响应摘要（不存原文，避免日志爆炸）"""
    if response_obj is None:
        return None
    summary: dict[str, Any] = {}
    with suppress(Exception):
        choices = getattr(response_obj, "choices", None) or []
        if choices:
            first = choices[0]
            msg = getattr(first, "message", None)
            if msg is not None:
                content = getattr(msg, "content", None) or ""
                summary["preview"] = content[:200] if isinstance(content, str) else None
                summary["finish_reason"] = getattr(first, "finish_reason", None)
    return summary or None


async def _persist_event(
    *,
    kwargs: dict[str, Any],
    response_obj: Any,
    start_time: Any,
    end_time: Any,
    status: str,
    error_code: str | None,
    error_message: str | None,
) -> None:
    """把单次调用持久化到 DB + Redis"""

    metadata = kwargs.get("metadata") or kwargs.get("litellm_metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    team_id = _to_uuid(metadata.get("gateway_team_id"))
    user_id = _to_uuid(metadata.get("gateway_user_id"))
    vkey_id = _to_uuid(metadata.get("gateway_vkey_id"))

    capability = str(metadata.get("gateway_capability", "chat"))
    route_name = metadata.get("gateway_route_name") or kwargs.get("model")
    real_model = (
        getattr(response_obj, "model", None)
        or kwargs.get("model")
    )
    provider = metadata.get("gateway_provider")

    input_tokens, output_tokens, cached_tokens = _extract_usage(response_obj)
    cost_usd = _calc_cost(kwargs, response_obj) if status == "success" else Decimal("0")

    start_dt = _safe_dt(start_time)
    end_dt = _safe_dt(end_time) or datetime.now(UTC)
    latency_ms = int((end_dt - start_dt).total_seconds() * 1000) if start_dt else 0
    ttfb_ms = metadata.get("gateway_ttfb_ms")
    if ttfb_ms is not None:
        with suppress(TypeError, ValueError):
            ttfb_ms = int(ttfb_ms)

    cache_hit = bool(metadata.get("gateway_cache_hit") or kwargs.get("cache_hit"))
    fallback_chain = metadata.get("gateway_fallback_chain") or []
    if isinstance(fallback_chain, str):
        fallback_chain = [fallback_chain]
    fallback_chain = [str(x) for x in fallback_chain if x]

    request_id = metadata.get("gateway_request_id") or kwargs.get("litellm_call_id")
    prompt_hash = metadata.get("pii_prompt_hash")
    pii_redactions = metadata.get("pii_redactions") or []
    prompt_redacted = (
        {"redactions": pii_redactions} if pii_redactions else None
    )

    response_summary = _summarize_response(response_obj)

    team_snapshot = metadata.get("gateway_team_snapshot")
    user_email_snapshot = metadata.get("gateway_user_email_snapshot")
    vkey_name_snapshot = metadata.get("gateway_vkey_name_snapshot")
    route_snapshot = metadata.get("gateway_route_snapshot")

    extra_metadata = {
        k: v
        for k, v in metadata.items()
        if not k.startswith("gateway_") and k not in {"pii_prompt_hash", "pii_redactions"}
    }
    metadata_extra = extra_metadata or None

    # ---------- 写 DB ----------
    try:
        from domains.gateway.infrastructure.repositories.request_log_repository import (
            RequestLogRepository,
        )

        async with get_session_context() as session:
            await RequestLogRepository(session).insert(
                team_id=team_id,
                user_id=user_id,
                vkey_id=vkey_id,
                team_snapshot=team_snapshot,
                user_email_snapshot=user_email_snapshot,
                vkey_name_snapshot=vkey_name_snapshot,
                route_snapshot=route_snapshot,
                capability=capability,
                route_name=str(route_name) if route_name else None,
                real_model=str(real_model) if real_model else None,
                provider=str(provider) if provider else None,
                status=status,
                error_code=error_code,
                error_message=error_message,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                ttfb_ms=ttfb_ms if isinstance(ttfb_ms, int) else None,
                cache_hit=cache_hit,
                fallback_chain=fallback_chain,
                request_id=str(request_id) if request_id else None,
                prompt_hash=str(prompt_hash) if prompt_hash else None,
                prompt_redacted=prompt_redacted,
                response_summary=response_summary,
                metadata_extra=metadata_extra,
            )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to persist gateway request log: %s", exc)

    # ---------- 写 Redis 实时计数 ----------
    with suppress(Exception):
        await _bump_redis_counters(
            team_id=str(team_id) if team_id else None,
            vkey_id=str(vkey_id) if vkey_id else None,
            user_id=str(user_id) if user_id else None,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )


async def _bump_redis_counters(
    *,
    team_id: str | None,
    vkey_id: str | None,
    user_id: str | None,
    status: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
) -> None:
    client = await get_redis_client()
    keys = _redis_keys(team_id, vkey_id, user_id)
    pipe = client.pipeline()
    bucket_minute = int(time.time() // 60)
    bucket_day = datetime.now(UTC).strftime("%Y%m%d")
    bucket_month = datetime.now(UTC).strftime("%Y%m")
    field = "ok" if status == "success" else "err"
    for key in keys:
        pipe.hincrby(f"{key}:m{bucket_minute}", "total", 1)
        pipe.hincrby(f"{key}:m{bucket_minute}", field, 1)
        pipe.expire(f"{key}:m{bucket_minute}", 3600)

        pipe.hincrby(f"{key}:d{bucket_day}", "total", 1)
        pipe.hincrby(f"{key}:d{bucket_day}", "tokens", input_tokens + output_tokens)
        pipe.hincrbyfloat(f"{key}:d{bucket_day}", "cost", float(cost_usd))
        pipe.expire(f"{key}:d{bucket_day}", 86400 * 35)

        pipe.hincrby(f"{key}:M{bucket_month}", "total", 1)
        pipe.hincrby(f"{key}:M{bucket_month}", "tokens", input_tokens + output_tokens)
        pipe.hincrbyfloat(f"{key}:M{bucket_month}", "cost", float(cost_usd))
        pipe.expire(f"{key}:M{bucket_month}", 86400 * 90)
    await pipe.execute()


__all__ = ["GatewayCustomLogger", "get_logger_singleton"]
