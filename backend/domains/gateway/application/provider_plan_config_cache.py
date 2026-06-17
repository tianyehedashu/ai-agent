"""代理热路径 ``provider_plans`` 活跃套餐配置缓存（L1 内存 + Redis，版本号失效）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import json
import time
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.period_reset_anchor import period_reset_anchor_from_plan_quota
from domains.gateway.domain.quota_plan import PlanQuotaSpec, normalize_reset_strategy
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from domains.gateway.infrastructure.models.provider_plan import (
        ProviderPlan,
        ProviderPlanQuota,
    )

logger = get_logger(__name__)

_TTL_SEC = 60.0
_NEG_TTL_SEC = 30.0
_LOCAL_MAX = 2048
_REDIS_VERSION_KEY = "gw:provider_plan_cfg:ver"
_REDIS_ENTRY_PREFIX = "gw:provider_plan_cfg:entry:"
_REDIS_EMPTY_MARKER = "\x00empty"

_MISS = object()

_LookupKey = tuple[uuid.UUID, str | None]
_LocalEntry = tuple["ProviderPlanConfigSnapshot | None", float]
_LOCAL: dict[tuple[str, uuid.UUID, str], _LocalEntry] = {}


@dataclass(frozen=True)
class ProviderPlanQuotaConfigRow:
    quota_id: uuid.UUID
    label: str
    window_seconds: int
    reset_strategy: str
    limit_usd: Decimal | None
    limit_tokens: int | None
    limit_requests: int | None
    reset_timezone: str = "UTC"
    reset_time_minutes: int = 0
    reset_day_of_month: int = 1


@dataclass(frozen=True)
class ProviderPlanConfigSnapshot:
    plan_id: uuid.UUID
    valid_from: datetime
    valid_until: datetime
    quotas: tuple[ProviderPlanQuotaConfigRow, ...]

    def is_active_at(self, when: datetime) -> bool:
        return self.valid_from <= when < self.valid_until


def plan_quota_specs_from_config(config: ProviderPlanConfigSnapshot) -> list[PlanQuotaSpec]:
    return [
        PlanQuotaSpec(
            quota_id=row.quota_id,
            label=row.label,
            window_seconds=row.window_seconds,
            limit_usd=row.limit_usd,
            limit_tokens=row.limit_tokens,
            limit_requests=row.limit_requests,
            reset_strategy=normalize_reset_strategy(row.reset_strategy),
            plan_valid_from=config.valid_from,
            period_reset_anchor=period_reset_anchor_from_plan_quota(
                reset_timezone=row.reset_timezone,
                reset_time_minutes=row.reset_time_minutes,
                reset_day_of_month=row.reset_day_of_month,
            ),
        )
        for row in config.quotas
    ]


def provider_plan_config_from_orm(
    plan: ProviderPlan,
    quotas: list[ProviderPlanQuota],
) -> ProviderPlanConfigSnapshot:
    return ProviderPlanConfigSnapshot(
        plan_id=plan.id,
        valid_from=plan.valid_from,
        valid_until=plan.valid_until,
        quotas=tuple(
            ProviderPlanQuotaConfigRow(
                quota_id=q.id,
                label=q.label,
                window_seconds=q.window_seconds,
                reset_strategy=q.reset_strategy,
                reset_timezone=q.reset_timezone,
                reset_time_minutes=q.reset_time_minutes,
                reset_day_of_month=q.reset_day_of_month,
                limit_usd=q.limit_usd,
                limit_tokens=q.limit_tokens,
                limit_requests=q.limit_requests,
            )
            for q in quotas
        ),
    )


def _lookup_key(credential_id: uuid.UUID, real_model: str | None) -> _LookupKey:
    model_key = (real_model or "").strip() or None
    return credential_id, model_key


def _coord_to_local_key(version: str, credential_id: uuid.UUID, real_model: str | None) -> tuple[
    str, uuid.UUID, str
]:
    _, model_key = _lookup_key(credential_id, real_model)
    return version, credential_id, model_key if model_key is not None else "_"


def _coord_to_redis_key(version: str, credential_id: uuid.UUID, real_model: str | None) -> str:
    _, model_key = _lookup_key(credential_id, real_model)
    model_seg = model_key if model_key is not None else "_"
    return f"{_REDIS_ENTRY_PREFIX}{version}:{credential_id}:{model_seg}"


async def get_cached_active_provider_plan(
    credential_id: uuid.UUID,
    real_model: str | None,
    *,
    now: datetime,
    loader: Callable[[], Awaitable[ProviderPlanConfigSnapshot | None]],
) -> ProviderPlanConfigSnapshot | None:
    """按 (credential_id, real_model) 缓存活跃套餐；``None`` 表示无活跃 plan（负缓存）。"""
    version = await _get_version()
    cached = _get_local(version, credential_id, real_model)
    if cached is _MISS:
        redis_hit = await _get_redis(version, credential_id, real_model)
        if redis_hit is not _MISS:
            if redis_hit is None:
                _put_local(version, credential_id, real_model, None)
            else:
                assert isinstance(redis_hit, ProviderPlanConfigSnapshot)
                _put_local(version, credential_id, real_model, redis_hit)
            cached = redis_hit

    if cached is not _MISS:
        if cached is None:
            return None
        assert isinstance(cached, ProviderPlanConfigSnapshot)
        if cached.is_active_at(now):
            return cached
        # 生命周期过期：当作未缓存，重新加载
        cached = _MISS

    loaded = await loader()
    if loaded is None:
        _put_local(version, credential_id, real_model, None)
        await _put_redis_tombstone(version, credential_id, real_model)
        return None

    if not loaded.is_active_at(now):
        _put_local(version, credential_id, real_model, None)
        await _put_redis_tombstone(version, credential_id, real_model)
        return None

    _put_local(version, credential_id, real_model, loaded)
    await _put_redis(version, credential_id, real_model, loaded)
    return loaded


async def invalidate_provider_plan_config_cache() -> None:
    """ProviderPlan / quota 变更后 bump 版本号，O(1) 失效全部热路径配置缓存。"""
    _LOCAL.clear()
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.incr(_REDIS_VERSION_KEY)
    except Exception:
        logger.warning("Redis provider plan config cache invalidate failed", exc_info=True)


def clear_provider_plan_config_cache_for_tests() -> None:
    _LOCAL.clear()


def _get_local(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
) -> ProviderPlanConfigSnapshot | None | object:
    key = _coord_to_local_key(version, credential_id, real_model)
    hit = _LOCAL.get(key)
    if hit is None:
        return _MISS
    row, ts = hit
    ttl = _TTL_SEC if row is not None else _NEG_TTL_SEC
    if time.monotonic() - ts >= ttl:
        _LOCAL.pop(key, None)
        return _MISS
    return row


def _put_local(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
    row: ProviderPlanConfigSnapshot | None,
) -> None:
    key = _coord_to_local_key(version, credential_id, real_model)
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[key] = (row, time.monotonic())


async def _get_redis(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
) -> ProviderPlanConfigSnapshot | None | object:
    redis = await _get_redis_client()
    if redis is None:
        return _MISS
    try:
        raw = await redis.get(_coord_to_redis_key(version, credential_id, real_model))
    except Exception:
        logger.warning("Redis provider plan config cache read failed", exc_info=True)
        return _MISS
    if raw is None:
        return _MISS
    decoded = raw.decode() if isinstance(raw, bytes) else raw
    if decoded == _REDIS_EMPTY_MARKER:
        return None
    try:
        return _decode_snapshot(json.loads(decoded))
    except (TypeError, ValueError, json.JSONDecodeError, KeyError):
        return _MISS


async def _put_redis(
    version: str,
    credential_id: uuid.UUID,
    real_model: str | None,
    row: ProviderPlanConfigSnapshot,
) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.set(
            _coord_to_redis_key(version, credential_id, real_model),
            json.dumps(_encode_snapshot(row)),
            ex=int(_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis provider plan config cache write failed", exc_info=True)


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
        logger.warning("Redis provider plan config tombstone write failed", exc_info=True)


def _encode_snapshot(row: ProviderPlanConfigSnapshot) -> dict[str, object]:
    return {
        "plan_id": str(row.plan_id),
        "valid_from": row.valid_from.astimezone(UTC).isoformat(),
        "valid_until": row.valid_until.astimezone(UTC).isoformat(),
        "quotas": [
            {
                "quota_id": str(q.quota_id),
                "label": q.label,
                "window_seconds": q.window_seconds,
                "reset_strategy": q.reset_strategy,
                "reset_timezone": q.reset_timezone,
                "reset_time_minutes": q.reset_time_minutes,
                "reset_day_of_month": q.reset_day_of_month,
                "limit_usd": str(q.limit_usd) if q.limit_usd is not None else None,
                "limit_tokens": q.limit_tokens,
                "limit_requests": q.limit_requests,
            }
            for q in row.quotas
        ],
    }


def _decode_snapshot(payload: dict[str, object]) -> ProviderPlanConfigSnapshot:
    quotas_raw = payload.get("quotas")
    quota_rows: list[ProviderPlanQuotaConfigRow] = []
    if isinstance(quotas_raw, list):
        for item in quotas_raw:
            if not isinstance(item, dict):
                continue
            quota_rows.append(
                ProviderPlanQuotaConfigRow(
                    quota_id=uuid.UUID(str(item["quota_id"])),
                    label=str(item["label"]),
                    window_seconds=int(item["window_seconds"]),
                    reset_strategy=str(item.get("reset_strategy") or "rolling"),
                    reset_timezone=str(item.get("reset_timezone") or "UTC"),
                    reset_time_minutes=int(item.get("reset_time_minutes") or 0),
                    reset_day_of_month=int(item.get("reset_day_of_month") or 1),
                    limit_usd=Decimal(str(item["limit_usd"]))
                    if item.get("limit_usd") is not None
                    else None,
                    limit_tokens=int(item["limit_tokens"])
                    if item.get("limit_tokens") is not None
                    else None,
                    limit_requests=int(item["limit_requests"])
                    if item.get("limit_requests") is not None
                    else None,
                )
            )
    return ProviderPlanConfigSnapshot(
        plan_id=uuid.UUID(str(payload["plan_id"])),
        valid_from=datetime.fromisoformat(str(payload["valid_from"])),
        valid_until=datetime.fromisoformat(str(payload["valid_until"])),
        quotas=tuple(quota_rows),
    )


async def _get_version() -> str:
    redis = await _get_redis_client()
    if redis is None:
        return "0"
    try:
        raw = await redis.get(_REDIS_VERSION_KEY)
        return raw.decode() if isinstance(raw, bytes) else (raw or "0")
    except Exception:
        logger.warning("Redis provider plan config version read failed", exc_info=True)
        return "0"


async def _get_redis_client():
    try:
        from libs.db.redis import get_redis_client

        return await get_redis_client()
    except Exception:
        return None


__all__ = [
    "ProviderPlanConfigSnapshot",
    "ProviderPlanQuotaConfigRow",
    "clear_provider_plan_config_cache_for_tests",
    "get_cached_active_provider_plan",
    "invalidate_provider_plan_config_cache",
    "plan_quota_specs_from_config",
    "provider_plan_config_from_orm",
]
