"""代理热路径 ``gateway_budgets`` 配置行缓存（L1 内存 + Redis，版本号失效）。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
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
_REDIS_ENTRY_PREFIX = "gw:budget_cfg:entry:"

_Coord = tuple[str, uuid.UUID | None, str, str | None]
_LocalEntry = tuple["BudgetConfigRow", float]
_LOCAL: dict[tuple[str, *_Coord], _LocalEntry] = {}


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


def _coord_to_local_key(version: str, coord: _Coord) -> tuple[str, *_Coord]:
    return (version, *coord)


def _coord_to_redis_key(version: str, coord: _Coord) -> str:
    target_kind, target_id, period, model_name = coord
    tid = str(target_id) if target_id is not None else "_"
    mname = model_name if model_name is not None else "_"
    return f"{_REDIS_ENTRY_PREFIX}{version}:{target_kind}:{tid}:{period}:{mname}"


async def get_cached_budget_by_plan(
    plan: tuple[BudgetCheckQuery, ...],
    loader: Callable[[], Awaitable[dict[_Coord, GatewayBudget]]],
) -> dict[_Coord, BudgetConfigRow]:
    """按 coord 细粒度缓存：先逐条命中本地/Redis，未命中部分批量查库并逐条回填。"""
    if not plan:
        return {}
    version = await _get_version()

    hits: dict[_Coord, BudgetConfigRow] = {}
    misses: list[BudgetCheckQuery] = []

    # 1. 本地缓存逐条命中
    for query in plan:
        coord: _Coord = (query.target_kind, query.target_id, query.period, query.model_name)
        row = _get_local_by_coord(version, coord)
        if row is not None:
            hits[coord] = row
        else:
            misses.append(query)

    # 2. Redis 逐条命中
    redis_misses: list[BudgetCheckQuery] = []
    for query in misses:
        coord = (query.target_kind, query.target_id, query.period, query.model_name)
        row = await _get_redis_by_coord(version, coord)
        if row is not None:
            hits[coord] = row
            _put_local_by_coord(version, coord, row)
        else:
            redis_misses.append(query)

    if not redis_misses:
        return hits

    # 3. 批量查库（仍查整个 plan，利用 get_many_by_plan 的 OR 查询效率）
    raw = await loader()
    for row in raw.values():
        config = budget_config_row_from_orm(row)
        coord = budget_config_coord_key(config)
        hits[coord] = config
        _put_local_by_coord(version, coord, config)
        await _put_redis_by_coord(version, coord, config)
    return hits


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


def _get_local_by_coord(version: str, coord: _Coord) -> BudgetConfigRow | None:
    key = _coord_to_local_key(version, coord)
    hit = _LOCAL.get(key)
    if hit is None:
        return None
    row, ts = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _LOCAL.pop(key, None)
        return None
    return row


def _put_local_by_coord(version: str, coord: _Coord, row: BudgetConfigRow) -> None:
    key = _coord_to_local_key(version, coord)
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[key] = (row, time.monotonic())


async def _get_redis_by_coord(version: str, coord: _Coord) -> BudgetConfigRow | None:
    redis = await _get_redis_client()
    if redis is None:
        return None
    try:
        raw = await redis.get(_coord_to_redis_key(version, coord))
    except Exception:
        logger.warning("Redis budget config cache read failed", exc_info=True)
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        tid = uuid.UUID(payload["target_id"]) if payload.get("target_id") else None
        return BudgetConfigRow(
            target_kind=payload["target_kind"],
            target_id=tid,
            period=payload["period"],
            model_name=payload.get("model_name"),
            limit_usd=Decimal(payload["limit_usd"])
            if payload.get("limit_usd") is not None
            else None,
            limit_tokens=payload.get("limit_tokens"),
            limit_requests=payload.get("limit_requests"),
        )
    except (TypeError, ValueError, json.JSONDecodeError, KeyError):
        return None


async def _put_redis_by_coord(version: str, coord: _Coord, row: BudgetConfigRow) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    payload = {
        "target_kind": row.target_kind,
        "target_id": str(row.target_id) if row.target_id is not None else None,
        "period": row.period,
        "model_name": row.model_name,
        "limit_usd": str(row.limit_usd) if row.limit_usd is not None else None,
        "limit_tokens": row.limit_tokens,
        "limit_requests": row.limit_requests,
    }
    try:
        await redis.set(
            _coord_to_redis_key(version, coord),
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
]
