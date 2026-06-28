"""代理热路径下游 ``entitlement_plans`` + ``entitlement_plan_quotas`` 配置缓存。

结构与 ``provider_quota_config_cache`` 对称（L1 内存 + Redis，版本号失效）：
- 键维度为 (scope, scope_id)，即 vkey_id / apikey_grant_id；
- 缓存该 scope 下全部 plan（按 ``created_at`` 倒序，复刻 DB 选取语义）及其 quotas；
- ``EntitlementGuard`` 在内存里做 model/capability 白名单过滤 + enforceable 过滤，
  从而消除转发热路径上每请求 2 次 DB 查询。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import json
import time
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.quota.period_reset_anchor import period_reset_anchor_from_plan_quota
from domains.gateway.domain.quota.quota_plan import PlanQuotaSpec, normalize_reset_strategy
from domains.gateway.domain.quota.quota_window_enforcement import is_quota_row_enforceable
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from domains.gateway.infrastructure.models.entitlement_plan import (
        EntitlementPlan,
        EntitlementPlanQuota,
    )

logger = get_logger(__name__)

_TTL_SEC = 60.0
_NEG_TTL_SEC = 30.0
_LOCAL_MAX = 2048
_REDIS_VERSION_KEY = "gw:entitlement_cfg:ver"
_REDIS_ENTRY_PREFIX = "gw:entitlement_cfg:entry:"
_REDIS_EMPTY_MARKER = "\x00empty"

_MISS = object()

_LocalEntry = tuple[tuple["EntitlementPlanConfigRow", ...], float]
_LOCAL: dict[tuple[str, str, str], _LocalEntry] = {}


@dataclass(frozen=True)
class EntitlementQuotaConfigRow:
    quota_id: uuid.UUID
    label: str
    window_seconds: int
    reset_strategy: str
    limit_usd: Decimal | None
    limit_tokens: int | None
    limit_requests: int | None
    unit_price_usd_per_token: Decimal | None
    unit_price_usd_per_request: Decimal | None
    reset_timezone: str = "UTC"
    reset_time_minutes: int = 0
    reset_day_of_month: int = 1
    enabled: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    limit_images: int | None = None


@dataclass(frozen=True)
class EntitlementPlanConfigRow:
    plan_id: uuid.UUID
    label: str
    included_models: tuple[str, ...]
    included_capabilities: tuple[str, ...]
    quotas: tuple[EntitlementQuotaConfigRow, ...]


def entitlement_quota_to_spec(row: EntitlementQuotaConfigRow) -> PlanQuotaSpec:
    return PlanQuotaSpec(
        quota_id=row.quota_id,
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


def select_active_plan_config(
    rows: tuple[EntitlementPlanConfigRow, ...],
    *,
    virtual_model: str | None,
    capability: str | None,
) -> EntitlementPlanConfigRow | None:
    """复刻 ``get_active_for_scope``：按缓存顺序（created_at 倒序）取首个匹配白名单的 plan。"""
    for row in rows:
        if (
            row.included_models
            and virtual_model is not None
            and virtual_model not in row.included_models
        ):
            continue
        if (
            row.included_capabilities
            and capability is not None
            and capability not in row.included_capabilities
        ):
            continue
        return row
    return None


def enforceable_quotas(
    plan: EntitlementPlanConfigRow,
    *,
    now: datetime | None = None,
) -> tuple[EntitlementQuotaConfigRow, ...]:
    when = now or datetime.now(UTC)
    return tuple(
        q
        for q in plan.quotas
        if is_quota_row_enforceable(
            enabled=q.enabled,
            valid_from=q.valid_from,
            valid_until=q.valid_until,
            now=when,
        )
    )


def entitlement_plan_rows_from_orm(
    pairs: list[tuple[EntitlementPlan, list[EntitlementPlanQuota]]],
) -> tuple[EntitlementPlanConfigRow, ...]:
    """ORM (plan, quotas) → 缓存行；按 ``created_at`` 倒序复刻活跃 plan 选取语义。"""
    ordered = sorted(
        pairs,
        key=lambda pq: pq[0].created_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return tuple(
        EntitlementPlanConfigRow(
            plan_id=plan.id,
            label=plan.label,
            included_models=tuple(plan.included_models or []),
            included_capabilities=tuple(plan.included_capabilities or []),
            quotas=tuple(
                EntitlementQuotaConfigRow(
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
                    unit_price_usd_per_token=q.unit_price_usd_per_token,
                    unit_price_usd_per_request=q.unit_price_usd_per_request,
                    enabled=q.enabled,
                    valid_from=q.valid_from,
                    valid_until=q.valid_until,
                    limit_images=getattr(q, "limit_images", None),
                )
                for q in quotas
            ),
        )
        for plan, quotas in ordered
    )


async def get_cached_entitlement_plans(
    scope: str,
    scope_id: uuid.UUID,
    *,
    loader: Callable[[], Awaitable[tuple[EntitlementPlanConfigRow, ...]]],
) -> tuple[EntitlementPlanConfigRow, ...]:
    version = await _get_version()
    cached = _get_local(version, scope, scope_id)
    if cached is _MISS:
        redis_hit = await _get_redis(version, scope, scope_id)
        if redis_hit is not _MISS:
            _put_local(version, scope, scope_id, redis_hit)
            cached = redis_hit

    if cached is not _MISS:
        assert isinstance(cached, tuple)
        return cached

    loaded = await loader()
    _put_local(version, scope, scope_id, loaded)
    if loaded:
        await _put_redis(version, scope, scope_id, loaded)
    else:
        await _put_redis_tombstone(version, scope, scope_id)
    return loaded


async def invalidate_entitlement_config_cache() -> None:
    _LOCAL.clear()
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.incr(_REDIS_VERSION_KEY)
    except Exception:
        logger.warning("Redis entitlement config cache invalidate failed", exc_info=True)


def clear_entitlement_config_cache_for_tests() -> None:
    _LOCAL.clear()


def _local_key(version: str, scope: str, scope_id: uuid.UUID) -> tuple[str, str, str]:
    return version, scope, str(scope_id)


def _redis_key(version: str, scope: str, scope_id: uuid.UUID) -> str:
    return f"{_REDIS_ENTRY_PREFIX}{version}:{scope}:{scope_id}"


def _get_local(
    version: str, scope: str, scope_id: uuid.UUID
) -> tuple[EntitlementPlanConfigRow, ...] | object:
    key = _local_key(version, scope, scope_id)
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
    scope: str,
    scope_id: uuid.UUID,
    rows: tuple[EntitlementPlanConfigRow, ...],
) -> None:
    key = _local_key(version, scope, scope_id)
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[key] = (rows, time.monotonic())


async def _get_redis(
    version: str, scope: str, scope_id: uuid.UUID
) -> tuple[EntitlementPlanConfigRow, ...] | object:
    redis = await _get_redis_client()
    if redis is None:
        return _MISS
    try:
        raw = await redis.get(_redis_key(version, scope, scope_id))
    except Exception:
        logger.warning("Redis entitlement config cache read failed", exc_info=True)
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
    scope: str,
    scope_id: uuid.UUID,
    rows: tuple[EntitlementPlanConfigRow, ...],
) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.set(
            _redis_key(version, scope, scope_id),
            json.dumps(_encode_rows(rows)),
            ex=int(_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis entitlement config cache write failed", exc_info=True)


async def _put_redis_tombstone(version: str, scope: str, scope_id: uuid.UUID) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.set(
            _redis_key(version, scope, scope_id),
            _REDIS_EMPTY_MARKER,
            ex=int(_NEG_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis entitlement config tombstone write failed", exc_info=True)


def _encode_quota(q: EntitlementQuotaConfigRow) -> dict[str, object]:
    return {
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
        "limit_images": q.limit_images,
        "unit_price_usd_per_token": str(q.unit_price_usd_per_token)
        if q.unit_price_usd_per_token is not None
        else None,
        "unit_price_usd_per_request": str(q.unit_price_usd_per_request)
        if q.unit_price_usd_per_request is not None
        else None,
        "enabled": q.enabled,
        "valid_from": q.valid_from.astimezone(UTC).isoformat() if q.valid_from else None,
        "valid_until": q.valid_until.astimezone(UTC).isoformat() if q.valid_until else None,
    }


def _encode_rows(rows: tuple[EntitlementPlanConfigRow, ...]) -> list[dict[str, object]]:
    return [
        {
            "plan_id": str(r.plan_id),
            "label": r.label,
            "included_models": list(r.included_models),
            "included_capabilities": list(r.included_capabilities),
            "quotas": [_encode_quota(q) for q in r.quotas],
        }
        for r in rows
    ]


def _decode_decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value not in (None, "") else None


def _decode_quota(item: dict[str, object]) -> EntitlementQuotaConfigRow:
    return EntitlementQuotaConfigRow(
        quota_id=uuid.UUID(str(item["quota_id"])),
        label=str(item["label"]),
        window_seconds=int(item["window_seconds"]),  # type: ignore[arg-type]
        reset_strategy=str(item.get("reset_strategy") or "rolling"),
        reset_timezone=str(item.get("reset_timezone") or "UTC"),
        reset_time_minutes=int(item.get("reset_time_minutes") or 0),  # type: ignore[arg-type]
        reset_day_of_month=int(item.get("reset_day_of_month") or 1),  # type: ignore[arg-type]
        limit_usd=_decode_decimal(item.get("limit_usd")),
        limit_tokens=int(item["limit_tokens"]) if item.get("limit_tokens") else None,  # type: ignore[arg-type]
        limit_requests=int(item["limit_requests"]) if item.get("limit_requests") else None,  # type: ignore[arg-type]
        limit_images=int(item["limit_images"]) if item.get("limit_images") else None,  # type: ignore[arg-type]
        unit_price_usd_per_token=_decode_decimal(item.get("unit_price_usd_per_token")),
        unit_price_usd_per_request=_decode_decimal(item.get("unit_price_usd_per_request")),
        enabled=bool(item.get("enabled", True)),
        valid_from=datetime.fromisoformat(str(item["valid_from"]))
        if item.get("valid_from")
        else None,
        valid_until=datetime.fromisoformat(str(item["valid_until"]))
        if item.get("valid_until")
        else None,
    )


def _decode_rows(payload: list[object]) -> tuple[EntitlementPlanConfigRow, ...]:
    rows: list[EntitlementPlanConfigRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        quotas_raw = item.get("quotas")
        quotas = (
            tuple(_decode_quota(q) for q in quotas_raw if isinstance(q, dict))
            if isinstance(quotas_raw, list)
            else ()
        )
        rows.append(
            EntitlementPlanConfigRow(
                plan_id=uuid.UUID(str(item["plan_id"])),
                label=str(item["label"]),
                included_models=tuple(str(m) for m in (item.get("included_models") or [])),
                included_capabilities=tuple(
                    str(c) for c in (item.get("included_capabilities") or [])
                ),
                quotas=quotas,
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
        logger.warning("Redis entitlement config version read failed", exc_info=True)
        return "0"


async def _get_redis_client():
    try:
        from libs.db.redis import get_redis_client

        return await get_redis_client()
    except Exception:
        return None


__all__ = [
    "EntitlementPlanConfigRow",
    "EntitlementQuotaConfigRow",
    "clear_entitlement_config_cache_for_tests",
    "enforceable_quotas",
    "entitlement_plan_rows_from_orm",
    "entitlement_quota_to_spec",
    "get_cached_entitlement_plans",
    "invalidate_entitlement_config_cache",
    "select_active_plan_config",
]
