"""代理热路径 ``provider_quotas`` 扁平规则配置缓存（L1 内存 + Redis，版本号失效）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import json
import time
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.period_reset_anchor import period_reset_anchor_from_plan_quota
from domains.gateway.domain.policies.quota_window_enforcement import is_quota_row_enforceable
from domains.gateway.domain.quota_plan import PlanQuotaSpec, normalize_reset_strategy
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from domains.gateway.infrastructure.models.provider_quota import ProviderQuota

logger = get_logger(__name__)

_TTL_SEC = 60.0
_NEG_TTL_SEC = 30.0
_LOCAL_MAX = 2048
_REDIS_VERSION_KEY = "gw:provider_quota_cfg:ver"
_REDIS_ENTRY_PREFIX = "gw:provider_quota_cfg:entry:"
_REDIS_EMPTY_MARKER = "\x00empty"

_MISS = object()

_LookupKey = tuple[uuid.UUID, str | None]
_LocalEntry = tuple[tuple["ProviderQuotaConfigRow", ...], float]
_LOCAL: dict[tuple[str, uuid.UUID, str], _LocalEntry] = {}


@dataclass(frozen=True)
class ProviderQuotaConfigRow:
    rule_id: uuid.UUID
    label: str
    window_seconds: int
    reset_strategy: str
    limit_usd: Decimal | None
    limit_tokens: int | None
    limit_requests: int | None
    reset_timezone: str = "UTC"
    reset_time_minutes: int = 0
    reset_day_of_month: int = 1
    enabled: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    limit_images: int | None = None


def quota_row_to_spec(row: ProviderQuotaConfigRow) -> PlanQuotaSpec:
    return PlanQuotaSpec(
        quota_id=row.rule_id,
        label=row.label,
        window_seconds=row.window_seconds,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        limit_images=row.limit_images,
        reset_strategy=normalize_reset_strategy(row.reset_strategy),
        period_reset_anchor=period_reset_anchor_from_plan_quota(
            reset_timezone=row.reset_timezone,
            reset_time_minutes=row.reset_time_minutes,
            reset_day_of_month=row.reset_day_of_month,
        ),
    )


def enforceable_specs_from_rows(
    rows: tuple[ProviderQuotaConfigRow, ...],
    *,
    now: datetime | None = None,
) -> list[PlanQuotaSpec]:
    when = now or datetime.now(UTC)
    return [
        quota_row_to_spec(row)
        for row in rows
        if is_quota_row_enforceable(
            enabled=row.enabled,
            valid_from=row.valid_from,
            valid_until=row.valid_until,
            now=when,
        )
    ]


def provider_quota_rows_from_orm(rules: list[ProviderQuota]) -> tuple[ProviderQuotaConfigRow, ...]:
    return tuple(
        ProviderQuotaConfigRow(
            rule_id=q.id,
            label=q.label,
            window_seconds=q.window_seconds,
            reset_strategy=q.reset_strategy,
            reset_timezone=q.reset_timezone,
            reset_time_minutes=q.reset_time_minutes,
            reset_day_of_month=q.reset_day_of_month,
            limit_usd=q.limit_usd,
            limit_tokens=q.limit_tokens,
            limit_requests=q.limit_requests,
            enabled=q.enabled,
            valid_from=q.valid_from,
            valid_until=q.valid_until,
            limit_images=getattr(q, "limit_images", None),
        )
        for q in rules
    )


def _lookup_key(credential_id: uuid.UUID, real_model: str | None) -> _LookupKey:
    model_key = (real_model or "").strip() or None
    return credential_id, model_key


def _coord_to_local_key(
    version: str, credential_id: uuid.UUID, real_model: str | None
) -> tuple[str, uuid.UUID, str]:
    _, model_key = _lookup_key(credential_id, real_model)
    return version, credential_id, model_key if model_key is not None else "_"


def _coord_to_redis_key(version: str, credential_id: uuid.UUID, real_model: str | None) -> str:
    _, model_key = _lookup_key(credential_id, real_model)
    model_seg = model_key if model_key is not None else "_"
    return f"{_REDIS_ENTRY_PREFIX}{version}:{credential_id}:{model_seg}"


async def get_cached_provider_quotas(
    credential_id: uuid.UUID,
    real_model: str | None,
    *,
    loader: Callable[[], Awaitable[tuple[ProviderQuotaConfigRow, ...]]],
) -> tuple[ProviderQuotaConfigRow, ...]:
    version = await _get_version()
    cached = _get_local(version, credential_id, real_model)
    if cached is _MISS:
        redis_hit = await _get_redis(version, credential_id, real_model)
        if redis_hit is not _MISS:
            _put_local(version, credential_id, real_model, redis_hit)
            cached = redis_hit

    if cached is not _MISS:
        assert isinstance(cached, tuple)
        return cached

    loaded = await loader()
    _put_local(version, credential_id, real_model, loaded)
    if loaded:
        await _put_redis(version, credential_id, real_model, loaded)
    else:
        await _put_redis_tombstone(version, credential_id, real_model)
    return loaded


async def invalidate_provider_quota_config_cache() -> None:
    _LOCAL.clear()
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.incr(_REDIS_VERSION_KEY)
    except Exception:
        logger.warning("Redis provider quota config cache invalidate failed", exc_info=True)


def clear_provider_quota_config_cache_for_tests() -> None:
    _LOCAL.clear()


def _get_local(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
) -> tuple[ProviderQuotaConfigRow, ...] | object:
    key = _coord_to_local_key(version, credential_id, real_model)
    hit = _LOCAL.get(key)
    if hit is None:
        return _MISS
    rows, ts = hit
    ttl = _TTL_SEC if rows else _NEG_TTL_SEC
    if time.monotonic() - ts >= ttl:
        _LOCAL.pop(key, None)
        return _MISS
    return rows


def _put_local(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
    rows: tuple[ProviderQuotaConfigRow, ...],
) -> None:
    key = _coord_to_local_key(version, credential_id, real_model)
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[key] = (rows, time.monotonic())


async def _get_redis(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
) -> tuple[ProviderQuotaConfigRow, ...] | object:
    redis = await _get_redis_client()
    if redis is None:
        return _MISS
    try:
        raw = await redis.get(_coord_to_redis_key(version, credential_id, real_model))
    except Exception:
        logger.warning("Redis provider quota config cache read failed", exc_info=True)
        return _MISS
    if raw is None:
        return _MISS
    decoded = raw.decode() if isinstance(raw, bytes) else raw
    if decoded == _REDIS_EMPTY_MARKER:
        return ()
    try:
        return _decode_rows(json.loads(decoded))
    except (TypeError, ValueError, json.JSONDecodeError, KeyError):
        return _MISS


async def _put_redis(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
    rows: tuple[ProviderQuotaConfigRow, ...],
) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.set(
            _coord_to_redis_key(version, credential_id, real_model),
            json.dumps(_encode_rows(rows)),
            ex=int(_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis provider quota config cache write failed", exc_info=True)


async def _put_redis_tombstone(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.set(
            _coord_to_redis_key(version, credential_id, real_model),
            _REDIS_EMPTY_MARKER,
            ex=int(_NEG_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis provider quota config tombstone write failed", exc_info=True)


def _encode_rows(rows: tuple[ProviderQuotaConfigRow, ...]) -> list[dict[str, object]]:
    return [
        {
            "rule_id": str(r.rule_id),
            "label": r.label,
            "window_seconds": r.window_seconds,
            "reset_strategy": r.reset_strategy,
            "reset_timezone": r.reset_timezone,
            "reset_time_minutes": r.reset_time_minutes,
            "reset_day_of_month": r.reset_day_of_month,
            "limit_usd": str(r.limit_usd) if r.limit_usd is not None else None,
            "limit_tokens": r.limit_tokens,
            "limit_requests": r.limit_requests,
            "limit_images": r.limit_images,
            "enabled": r.enabled,
            "valid_from": r.valid_from.astimezone(UTC).isoformat() if r.valid_from else None,
            "valid_until": r.valid_until.astimezone(UTC).isoformat() if r.valid_until else None,
        }
        for r in rows
    ]


def _decode_rows(payload: list[object]) -> tuple[ProviderQuotaConfigRow, ...]:
    rows: list[ProviderQuotaConfigRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rows.append(
            ProviderQuotaConfigRow(
                rule_id=uuid.UUID(str(item["rule_id"])),
                label=str(item["label"]),
                window_seconds=int(item["window_seconds"]),
                reset_strategy=str(item.get("reset_strategy") or "rolling"),
                reset_timezone=str(item.get("reset_timezone") or "UTC"),
                reset_time_minutes=int(item.get("reset_time_minutes") or 0),
                reset_day_of_month=int(item.get("reset_day_of_month") or 1),
                limit_usd=Decimal(str(item["limit_usd"])) if item.get("limit_usd") else None,
                limit_tokens=int(item["limit_tokens"]) if item.get("limit_tokens") else None,
                limit_requests=int(item["limit_requests"]) if item.get("limit_requests") else None,
                limit_images=int(item["limit_images"]) if item.get("limit_images") else None,
                enabled=bool(item.get("enabled", True)),
                valid_from=datetime.fromisoformat(str(item["valid_from"]))
                if item.get("valid_from")
                else None,
                valid_until=datetime.fromisoformat(str(item["valid_until"]))
                if item.get("valid_until")
                else None,
            )
        )
    return tuple(rows)


async def _get_version() -> str:
    redis = await _get_redis_client()
    if redis is None:
        return "0"
    try:
        raw = await redis.get(_REDIS_VERSION_KEY)
        return raw.decode() if isinstance(raw, bytes) else (raw or "0")
    except Exception:
        logger.warning("Redis provider quota config version read failed", exc_info=True)
        return "0"


async def _get_redis_client():
    try:
        from libs.db.redis import get_redis_client

        return await get_redis_client()
    except Exception:
        return None


__all__ = [
    "ProviderQuotaConfigRow",
    "clear_provider_quota_config_cache_for_tests",
    "enforceable_specs_from_rows",
    "get_cached_provider_quotas",
    "invalidate_provider_quota_config_cache",
    "provider_quota_rows_from_orm",
    "quota_row_to_spec",
]
