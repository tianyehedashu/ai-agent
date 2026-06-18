"""代理热路径 ``gateway_budgets`` 配置行缓存（L1 内存 + Redis，版本号失效）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
import time
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    period_reset_anchor_from_row,
)
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from domains.gateway.domain.proxy_policy import BudgetCheckQuery
    from domains.gateway.infrastructure.models.budget import GatewayBudget

logger = get_logger(__name__)

_TTL_SEC = 60.0
# 负缓存（查无此行）TTL 取较短值，限制极端"失效漏发"下的陈旧窗口；
# 正常情况下写路径 bump 版本号即令旧版本全部 key（含墓碑）不可达。
_NEG_TTL_SEC = 30.0
_LOCAL_MAX = 2048
_REDIS_VERSION_KEY = "gw:budget_cfg:ver"
_REDIS_ENTRY_PREFIX = "gw:budget_cfg:entry:"
# Redis 墓碑标记：表示该坐标确无预算行（负缓存），与正常 JSON payload 区分。
_REDIS_EMPTY_MARKER = "\x00empty"

# 读缓存的三态：命中 BudgetConfigRow / 墓碑（None，已知无行）/ 未缓存（_MISS）。
_MISS = object()

# 坐标含 tenant_id（末位）：仅成员总量/模型护栏行非空，按团队隔离。
_Coord = tuple[str, uuid.UUID | None, str, str | None, uuid.UUID | None, uuid.UUID | None]
# 值为 None 表示墓碑（负缓存：该坐标确无预算行）。
_LocalEntry = tuple["BudgetConfigRow | None", float]
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
    credential_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    period_reset_anchor: PeriodResetAnchor = DEFAULT_PERIOD_RESET_ANCHOR
    # 启用停用 + 起止时间（执法侧据此决定是否纳入；NULL 起止 = 不限）
    enabled: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None


def budget_config_row_from_orm(row: GatewayBudget) -> BudgetConfigRow:
    return BudgetConfigRow(
        target_kind=row.target_kind,
        target_id=row.target_id,
        period=row.period,
        model_name=row.model_name,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        credential_id=row.credential_id,
        tenant_id=row.tenant_id,
        period_reset_anchor=period_reset_anchor_from_row(
            timezone=getattr(row, "period_timezone", None),
            time_minutes=getattr(row, "period_reset_minutes", None),
            day_of_month=getattr(row, "period_reset_day", None),
        ),
        enabled=getattr(row, "enabled", True),
        valid_from=getattr(row, "valid_from", None),
        valid_until=getattr(row, "valid_until", None),
    )


def budget_config_coord_key(row: BudgetConfigRow) -> _Coord:
    return (
        row.target_kind,
        row.target_id,
        row.period,
        row.model_name,
        row.credential_id,
        row.tenant_id,
    )


def _coord_to_local_key(version: str, coord: _Coord) -> tuple[str, *_Coord]:
    return (version, *coord)


def _coord_to_redis_key(version: str, coord: _Coord) -> str:
    target_kind, target_id, period, model_name, credential_id, tenant_id = coord
    tid = str(target_id) if target_id is not None else "_"
    mname = model_name if model_name is not None else "_"
    cid = str(credential_id) if credential_id is not None else "_"
    ten = str(tenant_id) if tenant_id is not None else "_"
    return f"{_REDIS_ENTRY_PREFIX}{version}:{target_kind}:{tid}:{period}:{mname}:{cid}:{ten}"


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

    # 1. 本地缓存逐条命中（墓碑 = 已知无行，直接跳过，不进 hits 也不查库）
    for query in plan:
        coord: _Coord = (
            query.target_kind,
            query.target_id,
            query.period,
            query.model_name,
            query.credential_id,
            query.tenant_id,
        )
        cached = _get_local_by_coord(version, coord)
        if cached is _MISS:
            misses.append(query)
        elif cached is not None:
            hits[coord] = cached  # type: ignore[assignment]

    # 2. Redis 逐条命中（命中 / 墓碑均回填 L1，避免重复查库）
    redis_misses: list[BudgetCheckQuery] = []
    for query in misses:
        coord = (
            query.target_kind,
            query.target_id,
            query.period,
            query.model_name,
            query.credential_id,
            query.tenant_id,
        )
        cached = await _get_redis_by_coord(version, coord)
        if cached is _MISS:
            redis_misses.append(query)
        elif cached is None:
            _put_local_by_coord(version, coord, None)
        else:
            hits[coord] = cached  # type: ignore[assignment]
            _put_local_by_coord(version, coord, cached)  # type: ignore[arg-type]

    if not redis_misses:
        return hits

    # 3. 批量查库（仍查整个 plan，利用 get_many_by_plan 的 OR 查询效率）
    raw = await loader()
    returned: set[_Coord] = set()
    for row in raw.values():
        config = budget_config_row_from_orm(row)
        coord = budget_config_coord_key(config)
        returned.add(coord)
        hits[coord] = config
        _put_local_by_coord(version, coord, config)
        await _put_redis_by_coord(version, coord, config)

    # 4. 对"查无此行"的坐标写墓碑（负缓存）：无预算主体后续请求即零查库
    for query in redis_misses:
        coord = (
            query.target_kind,
            query.target_id,
            query.period,
            query.model_name,
            query.credential_id,
            query.tenant_id,
        )
        if coord not in returned:
            _put_local_by_coord(version, coord, None)
            await _put_redis_tombstone(version, coord)
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


def _get_local_by_coord(version: str, coord: _Coord) -> BudgetConfigRow | None | object:
    """三态返回：``BudgetConfigRow`` 命中 / ``None`` 墓碑 / ``_MISS`` 未缓存或过期。"""
    key = _coord_to_local_key(version, coord)
    hit = _LOCAL.get(key)
    if hit is None:
        return _MISS
    row, ts = hit
    ttl = _TTL_SEC if row is not None else _NEG_TTL_SEC
    if time.monotonic() - ts >= ttl:
        _LOCAL.pop(key, None)
        return _MISS
    return row


def _put_local_by_coord(version: str, coord: _Coord, row: BudgetConfigRow | None) -> None:
    """``row=None`` 写入墓碑（负缓存）。"""
    key = _coord_to_local_key(version, coord)
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[key] = (row, time.monotonic())


async def _get_redis_by_coord(version: str, coord: _Coord) -> BudgetConfigRow | None | object:
    """三态返回：``BudgetConfigRow`` 命中 / ``None`` 墓碑 / ``_MISS`` 未缓存。"""
    redis = await _get_redis_client()
    if redis is None:
        return _MISS
    try:
        raw = await redis.get(_coord_to_redis_key(version, coord))
    except Exception:
        logger.warning("Redis budget config cache read failed", exc_info=True)
        return _MISS
    if raw is None:
        return _MISS
    decoded = raw.decode() if isinstance(raw, bytes) else raw
    if decoded == _REDIS_EMPTY_MARKER:
        return None
    try:
        payload = json.loads(raw)
        tid = uuid.UUID(payload["target_id"]) if payload.get("target_id") else None
        cid = uuid.UUID(payload["credential_id"]) if payload.get("credential_id") else None
        ten = uuid.UUID(payload["tenant_id"]) if payload.get("tenant_id") else None
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
            credential_id=cid,
            tenant_id=ten,
            period_reset_anchor=period_reset_anchor_from_row(
                timezone=payload.get("period_timezone"),
                time_minutes=payload.get("period_reset_minutes"),
                day_of_month=payload.get("period_reset_day"),
            ),
            enabled=bool(payload.get("enabled", True)),
            valid_from=datetime.fromisoformat(payload["valid_from"])
            if payload.get("valid_from")
            else None,
            valid_until=datetime.fromisoformat(payload["valid_until"])
            if payload.get("valid_until")
            else None,
        )
    except (TypeError, ValueError, json.JSONDecodeError, KeyError):
        return _MISS


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
        "credential_id": str(row.credential_id) if row.credential_id is not None else None,
        "tenant_id": str(row.tenant_id) if row.tenant_id is not None else None,
        "period_timezone": row.period_reset_anchor.timezone,
        "period_reset_minutes": row.period_reset_anchor.time_minutes,
        "period_reset_day": row.period_reset_anchor.day_of_month,
        "enabled": row.enabled,
        "valid_from": row.valid_from.isoformat() if row.valid_from is not None else None,
        "valid_until": row.valid_until.isoformat() if row.valid_until is not None else None,
    }
    try:
        await redis.set(
            _coord_to_redis_key(version, coord),
            json.dumps(payload),
            ex=int(_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis budget config cache write failed", exc_info=True)


async def _put_redis_tombstone(version: str, coord: _Coord) -> None:
    """写入"查无此行"墓碑（负缓存），短 TTL。"""
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.set(
            _coord_to_redis_key(version, coord),
            _REDIS_EMPTY_MARKER,
            ex=int(_NEG_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis budget config cache tombstone write failed", exc_info=True)


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
