"""代理热路径 ``gateway_budgets`` 配置行缓存（L1 内存 + Redis，版本号失效）。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import time
from typing import TYPE_CHECKING
import uuid

from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from domains.gateway.domain.proxy_policy import BudgetCheckQuery
    from domains.gateway.infrastructure.models.budget import GatewayBudget

logger = get_logger(__name__)

_TTL_SEC = 60.0
_LOCAL_MAX = 2048
_REDIS_VERSION_KEY = "gw:budget_cfg:ver"
_REDIS_ENTRY_PREFIX = "gw:budget_cfg:"

_LocalKey = tuple[str, str]
_LocalEntry = tuple[
    dict[tuple[str, uuid.UUID | None, str, str | None], "BudgetConfigRow"],
    float,
]
_LOCAL: dict[_LocalKey, _LocalEntry] = {}


@dataclass(frozen=True)
class BudgetConfigRow:
    """预算配置快照（不含 soft_limit，热路径仅 hard limit 阻断）。"""

    target_kind: str
    target_id: uuid.UUID | None
    period: str
    model_name: str | None
    limit_usd: Decimal | None
    limit_tokens: int | None
    limit_requests: int | None


def budget_config_row_from_orm(row: GatewayBudget) -> BudgetConfigRow:
    return BudgetConfigRow(
        target_kind=row.target_kind,
        target_id=row.target_id,
        period=row.period,
        model_name=row.model_name,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
    )


def budget_config_coord_key(
    row: BudgetConfigRow,
) -> tuple[str, uuid.UUID | None, str, str | None]:
    return (row.target_kind, row.target_id, row.period, row.model_name)


def plan_cache_fingerprint(plan: tuple[BudgetCheckQuery, ...] | list[BudgetCheckQuery]) -> str:
    parts = sorted(
        f"{q.target_kind}:{q.target_id}:{q.period}:{q.model_name or ''}" for q in plan
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


async def get_cached_budget_by_plan(
    plan: tuple[BudgetCheckQuery, ...],
    loader: Callable[[], Awaitable[dict[tuple[str, uuid.UUID | None, str, str | None], GatewayBudget]]],
) -> dict[tuple[str, uuid.UUID | None, str, str | None], BudgetConfigRow]:
    """命中返回配置快照；未命中经 ``loader`` 查库并回填缓存。"""
    if not plan:
        return {}
    version = await _get_version()
    fp = plan_cache_fingerprint(plan)
    local_key: _LocalKey = (version, fp)
    local_hit = _get_local(local_key)
    if local_hit is not None:
        return local_hit

    redis_hit = await _get_redis(local_key)
    if redis_hit is not None:
        _put_local(local_key, redis_hit)
        return redis_hit

    raw = await loader()
    snapshot: dict[tuple[str, uuid.UUID | None, str, str | None], BudgetConfigRow] = {}
    for row in raw.values():
        config = budget_config_row_from_orm(row)
        snapshot[budget_config_coord_key(config)] = config
    _put_local(local_key, snapshot)
    await _put_redis(local_key, snapshot)
    return snapshot


async def invalidate_budget_config_cache() -> None:
    """预算配置变更后 bump 版本号，O(1) 失效全部 plan 缓存。"""
    _LOCAL.clear()
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.incr(_REDIS_VERSION_KEY)
    except Exception:
        logger.warning("Redis budget config cache invalidate failed", exc_info=True)


def clear_budget_config_cache_for_tests() -> None:
    _LOCAL.clear()


async def _get_version() -> str:
    """每次从 Redis 读取版本号，避免多副本 INCR 后本进程仍用旧 version。"""
    redis = await _get_redis_client()
    if redis is None:
        return "0"
    try:
        raw = await redis.get(_REDIS_VERSION_KEY)
        return raw.decode() if isinstance(raw, bytes) else (raw or "0")
    except Exception:
        logger.warning("Redis budget config version read failed", exc_info=True)
        return "0"


def _get_local(key: _LocalKey) -> dict[tuple[str, uuid.UUID | None, str, str | None], BudgetConfigRow] | None:
    hit = _LOCAL.get(key)
    if hit is None:
        return None
    snapshot, ts = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _LOCAL.pop(key, None)
        return None
    return snapshot


def _put_local(
    key: _LocalKey,
    snapshot: dict[tuple[str, uuid.UUID | None, str, str | None], BudgetConfigRow],
) -> None:
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[key] = (snapshot, time.monotonic())


async def _get_redis(
    key: _LocalKey,
) -> dict[tuple[str, uuid.UUID | None, str, str | None], BudgetConfigRow] | None:
    redis = await _get_redis_client()
    if redis is None:
        return None
    version, fp = key
    try:
        raw = await redis.get(f"{_REDIS_ENTRY_PREFIX}{version}:{fp}")
    except Exception:
        logger.warning("Redis budget config cache read failed", exc_info=True)
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        out: dict[tuple[str, uuid.UUID | None, str, str | None], BudgetConfigRow] = {}
        for item in payload:
            tid = uuid.UUID(item["target_id"]) if item.get("target_id") else None
            row = BudgetConfigRow(
                target_kind=item["target_kind"],
                target_id=tid,
                period=item["period"],
                model_name=item.get("model_name"),
                limit_usd=Decimal(item["limit_usd"]) if item.get("limit_usd") is not None else None,
                limit_tokens=item.get("limit_tokens"),
                limit_requests=item.get("limit_requests"),
            )
            out[budget_config_coord_key(row)] = row
        return out
    except (TypeError, ValueError, json.JSONDecodeError, KeyError):
        return None


async def _put_redis(
    key: _LocalKey,
    snapshot: dict[tuple[str, uuid.UUID | None, str, str | None], BudgetConfigRow],
) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    version, fp = key
    payload = [
        {
            "target_kind": row.target_kind,
            "target_id": str(row.target_id) if row.target_id is not None else None,
            "period": row.period,
            "model_name": row.model_name,
            "limit_usd": str(row.limit_usd) if row.limit_usd is not None else None,
            "limit_tokens": row.limit_tokens,
            "limit_requests": row.limit_requests,
        }
        for row in snapshot.values()
    ]
    try:
        await redis.set(
            f"{_REDIS_ENTRY_PREFIX}{version}:{fp}",
            json.dumps(payload),
            ex=int(_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis budget config cache write failed", exc_info=True)


async def _get_redis_client():
    try:
        from libs.db.redis import get_redis_client

        return await get_redis_client()
    except Exception:
        return None


__all__ = [
    "BudgetConfigRow",
    "budget_config_coord_key",
    "budget_config_row_from_orm",
    "clear_budget_config_cache_for_tests",
    "get_cached_budget_by_plan",
    "invalidate_budget_config_cache",
    "plan_cache_fingerprint",
]
