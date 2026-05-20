"""下游价解析短 TTL 缓存（Redis + 进程内回退；改价时 invalidate）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import logging
import threading
from typing import Any
import uuid

from domains.gateway.application.pricing.pricing_service import ResolvedPricing
from domains.gateway.domain.pricing_calculator import PricingRate

logger = logging.getLogger(__name__)

_CACHE_TTL = timedelta(minutes=5)
_TTL_SECONDS = int(_CACHE_TTL.total_seconds())
_REDIS_PREFIX = "gateway:pricing:resolve:"
_lock = threading.Lock()
_local: dict[str, tuple[ResolvedPricing, datetime]] = {}


def pricing_resolution_cache_key(
    *,
    tenant_id: uuid.UUID | None,
    gateway_model_id: uuid.UUID | None,
    entitlement_plan_id: uuid.UUID | None,
    capability: str,
) -> str:
    return f"{tenant_id}:{gateway_model_id}:{entitlement_plan_id}:{capability}"


@dataclass(frozen=True)
class CacheStats:
    size: int


def _rate_to_dict(rate: PricingRate | None) -> dict[str, str] | None:
    if rate is None:
        return None
    out: dict[str, str] = {
        "input_cost_per_token": str(rate.input_cost_per_token),
        "output_cost_per_token": str(rate.output_cost_per_token),
    }
    if rate.cache_creation_input_token_cost is not None:
        out["cache_creation_input_token_cost"] = str(rate.cache_creation_input_token_cost)
    if rate.cache_read_input_token_cost is not None:
        out["cache_read_input_token_cost"] = str(rate.cache_read_input_token_cost)
    if rate.per_request_usd is not None:
        out["per_request_usd"] = str(rate.per_request_usd)
    return out


def _rate_from_dict(raw: dict[str, str] | None) -> PricingRate | None:
    if raw is None:
        return None
    return PricingRate(
        input_cost_per_token=Decimal(str(raw["input_cost_per_token"])),
        output_cost_per_token=Decimal(str(raw["output_cost_per_token"])),
        cache_creation_input_token_cost=(
            Decimal(str(raw["cache_creation_input_token_cost"]))
            if raw.get("cache_creation_input_token_cost") is not None
            else None
        ),
        cache_read_input_token_cost=(
            Decimal(str(raw["cache_read_input_token_cost"]))
            if raw.get("cache_read_input_token_cost") is not None
            else None
        ),
        per_request_usd=(
            Decimal(str(raw["per_request_usd"])) if raw.get("per_request_usd") is not None else None
        ),
    )


def _resolved_to_payload(resolved: ResolvedPricing) -> dict[str, Any]:
    return {
        "hit_chain": resolved.hit_chain,
        "upstream": _rate_to_dict(resolved.upstream),
        "downstream": _rate_to_dict(resolved.downstream),
        "downstream_strategy": (
            resolved.downstream_row.inheritance_strategy if resolved.downstream_row else None
        ),
    }


def _payload_to_resolved(payload: dict[str, Any]) -> ResolvedPricing:
    downstream = _rate_from_dict(payload.get("downstream"))
    if downstream is None:
        downstream = PricingRate(
            input_cost_per_token=Decimal("0"),
            output_cost_per_token=Decimal("0"),
        )
    return ResolvedPricing(
        upstream=_rate_from_dict(payload.get("upstream")),
        downstream=downstream,
        downstream_row=None,
        upstream_row=None,
        hit_chain=list(payload.get("hit_chain") or []),
    )


def _local_get(key: str) -> ResolvedPricing | None:
    now = datetime.now(UTC)
    with _lock:
        entry = _local.get(key)
        if entry is None:
            return None
        resolved, expires = entry
        if expires <= now:
            _local.pop(key, None)
            return None
        return resolved


def _local_set(key: str, resolved: ResolvedPricing) -> None:
    expires = datetime.now(UTC) + _CACHE_TTL
    with _lock:
        _local[key] = (resolved, expires)


async def _redis_get(key: str) -> ResolvedPricing | None:
    try:
        from libs.db.redis import get_redis_client

        client = await get_redis_client()
        raw = await client.get(f"{_REDIS_PREFIX}{key}")
        if raw is None:
            return None
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        return _payload_to_resolved(json.loads(text))
    except Exception as exc:
        logger.debug("pricing cache redis get failed: %s", exc)
        return None


async def _redis_set(key: str, resolved: ResolvedPricing) -> None:
    try:
        from libs.db.redis import get_redis_client

        client = await get_redis_client()
        payload = json.dumps(_resolved_to_payload(resolved))
        await client.set(f"{_REDIS_PREFIX}{key}", payload, ex=_TTL_SECONDS)
    except Exception as exc:
        logger.debug("pricing cache redis set failed: %s", exc)


async def get_cached_resolution_async(key: str) -> ResolvedPricing | None:
    hit = _local_get(key)
    if hit is not None:
        return hit
    redis_hit = await _redis_get(key)
    if redis_hit is not None:
        _local_set(key, redis_hit)
    return redis_hit


async def set_cached_resolution_async(key: str, resolved: ResolvedPricing) -> None:
    _local_set(key, resolved)
    await _redis_set(key, resolved)


def get_cached_resolution(key: str) -> ResolvedPricing | None:
    """同步读（仅进程内）；``PricingService`` 在 async 路径用 ``get_cached_resolution_async``。"""
    return _local_get(key)


def set_cached_resolution(key: str, resolved: ResolvedPricing) -> None:
    _local_set(key, resolved)


async def invalidate_pricing_resolution_cache(
    *,
    tenant_id: uuid.UUID | None = None,
    gateway_model_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
) -> int:
    tid = tenant_id if tenant_id is not None else team_id
    if team_id is not None and tenant_id is None:
        import warnings

        warnings.warn(
            "invalidate_pricing_resolution_cache(team_id=) is deprecated; use tenant_id=",
            DeprecationWarning,
            stacklevel=2,
        )
    removed = 0
    with _lock:
        if tid is None and gateway_model_id is None:
            removed = len(_local)
            _local.clear()
        else:
            keys = list(_local.keys())
            for key in keys:
                if tid is not None and not key.startswith(f"{tid}:"):
                    continue
                if gateway_model_id is not None and f":{gateway_model_id}:" not in f":{key}:":
                    continue
                _local.pop(key, None)
                removed += 1
    try:
        from libs.db.redis import get_redis_client

        client = await get_redis_client()

        async def _collect(pattern: str) -> list[bytes | str]:
            out: list[bytes | str] = []
            async for k in client.scan_iter(match=pattern):
                out.append(k)
            return out

        if tid is None and gateway_model_id is None:
            keys = await _collect(f"{_REDIS_PREFIX}*")
            if keys:
                await client.delete(*keys)
                removed += len(keys)
        elif tid is not None:
            keys = await _collect(f"{_REDIS_PREFIX}{tid}:*")
            if keys:
                await client.delete(*keys)
                removed += len(keys)
    except Exception as exc:
        logger.debug("pricing cache redis invalidate failed: %s", exc)
    return removed


def clear_pricing_resolution_cache_for_tests() -> None:
    with _lock:
        _local.clear()


def pricing_cache_stats() -> CacheStats:
    with _lock:
        return CacheStats(size=len(_local))


# 兼容旧 import
_cache_key = pricing_resolution_cache_key

__all__ = [
    "CacheStats",
    "clear_pricing_resolution_cache_for_tests",
    "get_cached_resolution",
    "get_cached_resolution_async",
    "invalidate_pricing_resolution_cache",
    "pricing_cache_stats",
    "pricing_resolution_cache_key",
    "set_cached_resolution",
    "set_cached_resolution_async",
]
