"""
BudgetService - 预算预扣 / 结算

策略：
- 预扣（reserve）：调用前根据估算 token / 请求数 增加 Redis 计数；如超限则拒绝
- 结算（commit）：调用后用真实 cost / token 写 Redis + DB（落账）
- 还原（release）：调用失败时把预扣的请求计数减回去

Redis 用于实时计数（高频读写）；GatewayBudget 表用于持久化每日/每月用量。
两者通过定时 rollup 任务同步。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import uuid

from domains.gateway.domain.errors import (
    BudgetExceededError,
    RateLimitExceededError,
)
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)


PERIOD_DAILY = "daily"
PERIOD_MONTHLY = "monthly"
PERIOD_TOTAL = "total"


def _model_segment_hash(model_name: str) -> str:
    return hashlib.sha256(model_name.encode("utf-8")).hexdigest()[:16]


def _redis_model_segment(budget_model_name: str | None) -> str | None:
    if budget_model_name is None:
        return None
    return _model_segment_hash(budget_model_name)


def redis_model_segment_for_budget(budget_model_name: str | None) -> str | None:
    return _redis_model_segment(budget_model_name)


def _bucket_key(
    target_kind: str,
    target_id: str | None,
    period: str,
    *,
    model_segment: str | None = None,
) -> str:
    """Redis key for budget current values"""
    sid = target_id or "system"
    if period == PERIOD_DAILY:
        suffix = datetime.now(UTC).strftime("%Y%m%d")
    elif period == PERIOD_MONTHLY:
        suffix = datetime.now(UTC).strftime("%Y%m")
    else:
        suffix = "total"
    base = f"gateway:budget:{target_kind}:{sid}:{period}:{suffix}"
    if model_segment:
        return f"{base}:m:{model_segment}"
    return base


def _legacy_team_bucket_key(
    target_kind: str,
    target_id: str | None,
    period: str,
    *,
    model_segment: str | None = None,
) -> str | None:
    """迁移期：``tenant`` 预算曾以 ``team`` 写入 Redis，读时合并旧 key。"""
    if target_kind != "tenant":
        return None
    return _bucket_key("team", target_id, period, model_segment=model_segment)


def _rate_key(target_kind: str, target_id: str | None, dimension: str) -> str:
    """Redis key for rpm/tpm windows (60 秒滚动桶)"""
    sid = target_id or "system"
    return f"gateway:rate:{target_kind}:{sid}:{dimension}"


@dataclass(frozen=True)
class BudgetUsageCoord:
    """Redis 用量桶坐标。"""

    target_kind: str
    target_id: str | None
    period: str
    model_segment: str | None


@dataclass
class BudgetCheckResult:
    """预扣结果"""

    allowed: bool
    reason: str | None = None
    used_usd: Decimal = Decimal("0")
    used_tokens: int = 0
    used_requests: int = 0


@dataclass
class ScopeIdentifier:
    """budget/rate 的目标 scope（多维度合一）"""

    team_id: uuid.UUID
    user_id: uuid.UUID | None
    vkey_id: uuid.UUID | None


class BudgetService:
    """预算 + 限流服务"""

    def __init__(
        self,
        repo_factory: object | None = None,  # 可注入 BudgetRepository 工厂
    ) -> None:
        self._repo_factory = repo_factory

    # ---------------------------------------------------------------------
    # 限流（vkey/team/user 维度）
    # ---------------------------------------------------------------------

    async def check_rate_limit(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        rpm_limit: int | None,
        tpm_limit: int | None,
        estimate_tokens: int = 0,
    ) -> None:
        """检查 rpm/tpm 是否超限；不通过抛 RateLimitExceededError

        采用 60s 滚动窗口（Redis Sorted Set）：
        - rpm: 每个请求加一条 timestamp
        - tpm: 每个请求加 estimate_tokens
        """
        client = await get_redis_client()
        now = datetime.now(UTC).timestamp()
        window_start = now - 60

        if rpm_limit and rpm_limit > 0:
            key = _rate_key(target_kind, target_id, "rpm")
            await client.zremrangebyscore(key, 0, window_start)
            count = await client.zcard(key)
            if count >= rpm_limit:
                raise RateLimitExceededError(scope=f"{target_kind}:rpm", retry_after=60)
            await client.zadd(key, {f"{now}:{uuid.uuid4()}": now})
            await client.expire(key, 90)

        if tpm_limit and tpm_limit > 0 and estimate_tokens > 0:
            key = _rate_key(target_kind, target_id, "tpm")
            await client.zremrangebyscore(key, 0, window_start)
            # 累加目前窗口内 token 数（成员名形如 "<tokens>:<uuid>"）
            current_tokens = 0
            members = await client.zrange(key, 0, -1, withscores=True)
            for member, _score in members:
                try:
                    payload = member.decode() if isinstance(member, bytes) else str(member)
                    parts = payload.split(":", 1)
                    if len(parts) == 2:
                        current_tokens += int(parts[0])
                except (ValueError, AttributeError):
                    continue
            if current_tokens + estimate_tokens > tpm_limit:
                raise RateLimitExceededError(scope=f"{target_kind}:tpm", retry_after=60)
            await client.zadd(key, {f"{estimate_tokens}:{uuid.uuid4()}": now})
            await client.expire(key, 90)

    # ---------------------------------------------------------------------
    # 预算预扣 / 结算
    # ---------------------------------------------------------------------

    async def _read_budget_usage(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        model_segment: str | None,
    ) -> tuple[Decimal, int, int]:
        batch = await self.read_budget_usage_batch(
            [
                BudgetUsageCoord(
                    target_kind=target_kind,
                    target_id=target_id,
                    period=period,
                    model_segment=model_segment,
                )
            ]
        )
        coord = BudgetUsageCoord(
            target_kind=target_kind,
            target_id=target_id,
            period=period,
            model_segment=model_segment,
        )
        return batch.get(coord, (Decimal("0"), 0, 0))

    async def read_budget_usage_batch(
        self,
        coords: list[BudgetUsageCoord],
    ) -> dict[BudgetUsageCoord, tuple[Decimal, int, int]]:
        """Pipeline 批量读取预算 Redis 桶（含 tenant→team 迁移期 legacy key）。"""
        if not coords:
            return {}
        unique_coords = list(dict.fromkeys(coords))
        client = await get_redis_client()

        key_entries: list[tuple[BudgetUsageCoord, str, bool]] = []
        for coord in unique_coords:
            primary = _bucket_key(
                coord.target_kind,
                coord.target_id,
                coord.period,
                model_segment=coord.model_segment,
            )
            key_entries.append((coord, primary, False))
            legacy = _legacy_team_bucket_key(
                coord.target_kind,
                coord.target_id,
                coord.period,
                model_segment=coord.model_segment,
            )
            if legacy is not None:
                key_entries.append((coord, legacy, True))

        pipe = client.pipeline()
        for _coord, key, _is_legacy in key_entries:
            pipe.hmget(key, ["cost", "tokens", "requests"])
        raw_results = await pipe.execute()

        out: dict[BudgetUsageCoord, tuple[Decimal, int, int]] = {
            c: (Decimal("0"), 0, 0) for c in unique_coords
        }
        for (coord, _key, _is_legacy), values in zip(key_entries, raw_results, strict=True):
            used_cost, used_tokens, used_requests = out[coord]
            cost_raw = values[0]
            tokens_raw = values[1]
            requests_raw = values[2]
            used_cost = max(
                used_cost,
                Decimal(cost_raw.decode() if cost_raw else "0"),
            )
            used_tokens = max(
                used_tokens,
                int(tokens_raw.decode() if tokens_raw else "0"),
            )
            used_requests = max(
                used_requests,
                int(requests_raw.decode() if requests_raw else "0"),
            )
            out[coord] = (used_cost, used_tokens, used_requests)
        return out

    async def check_budget(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        limit_usd: Decimal | None,
        limit_tokens: int | None,
        limit_requests: int | None,
        budget_model_name: str | None = None,
        prefetched_usage: tuple[Decimal, int, int] | None = None,
    ) -> BudgetCheckResult:
        """读取当前 budget 状态；超限返回 allowed=False

        当前 cost/tokens/requests 来自 Redis 桶，由 commit 异步累加。
        """
        seg = _redis_model_segment(budget_model_name)
        if prefetched_usage is not None:
            used_cost, used_tokens, used_requests = prefetched_usage
        else:
            used_cost, used_tokens, used_requests = await self._read_budget_usage(
                target_kind=target_kind,
                target_id=target_id,
                period=period,
                model_segment=seg,
            )

        if limit_usd is not None and 0 < limit_usd <= used_cost:
            return BudgetCheckResult(
                allowed=False,
                reason="usd",
                used_usd=used_cost,
                used_tokens=used_tokens,
                used_requests=used_requests,
            )
        if limit_tokens and 0 < limit_tokens <= used_tokens:
            return BudgetCheckResult(
                allowed=False,
                reason="tokens",
                used_usd=used_cost,
                used_tokens=used_tokens,
                used_requests=used_requests,
            )
        if limit_requests and 0 < limit_requests <= used_requests:
            return BudgetCheckResult(
                allowed=False,
                reason="requests",
                used_usd=used_cost,
                used_tokens=used_tokens,
                used_requests=used_requests,
            )
        return BudgetCheckResult(
            allowed=True,
            used_usd=used_cost,
            used_tokens=used_tokens,
            used_requests=used_requests,
        )

    async def reserve(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        limit_requests: int | None,
        limit_tokens: int | None = None,
        estimate_tokens: int = 0,
        budget_model_name: str | None = None,
    ) -> tuple[int, int]:
        """预扣请求名额与/或 token 估算（防止并发穿透）。

        返回 ``(reserved_requests, reserved_tokens)``。
        """
        reserve_requests = limit_requests is not None and limit_requests > 0
        reserve_tokens = limit_tokens is not None and limit_tokens > 0 and estimate_tokens > 0
        if not reserve_requests and not reserve_tokens:
            return (0, 0)

        client = await get_redis_client()
        seg = _redis_model_segment(budget_model_name)
        key = _bucket_key(target_kind, target_id, period, model_segment=seg)

        reserved_requests = 0
        reserved_tokens = 0

        if reserve_requests:
            assert limit_requests is not None
            new_value = await client.hincrby(key, "requests", 1)
            reserved_requests = 1
            if period == PERIOD_DAILY:
                await client.expire(key, 90000)
            elif period == PERIOD_MONTHLY:
                await client.expire(key, 86400 * 35)
            if new_value > limit_requests:
                await client.hincrby(key, "requests", -1)
                raise BudgetExceededError(
                    scope=target_kind,
                    period=period,
                    limit=float(limit_requests),
                    used=float(new_value - 1),
                )

        if reserve_tokens:
            assert limit_tokens is not None
            new_tokens = await client.hincrby(key, "tokens", estimate_tokens)
            reserved_tokens = estimate_tokens
            if period == PERIOD_DAILY:
                await client.expire(key, 90000)
            elif period == PERIOD_MONTHLY:
                await client.expire(key, 86400 * 35)
            if new_tokens > limit_tokens:
                if reserved_requests:
                    await client.hincrby(key, "requests", -1)
                await client.hincrby(key, "tokens", -estimate_tokens)
                raise BudgetExceededError(
                    scope=target_kind,
                    period=period,
                    limit=float(limit_tokens),
                    used=float(new_tokens - estimate_tokens),
                )

        return (reserved_requests, reserved_tokens)

    async def release(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        budget_model_name: str | None = None,
        reserved_requests: int = 1,
        reserved_tokens: int = 0,
    ) -> None:
        """请求失败时回滚预扣的请求数 / token 估算。"""
        if reserved_requests <= 0 and reserved_tokens <= 0:
            return
        client = await get_redis_client()
        seg = _redis_model_segment(budget_model_name)
        key = _bucket_key(target_kind, target_id, period, model_segment=seg)
        if reserved_requests > 0:
            await client.hincrby(key, "requests", -reserved_requests)
        if reserved_tokens > 0:
            await client.hincrby(key, "tokens", -reserved_tokens)

    async def commit(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        delta_cost: Decimal,
        delta_tokens: int,
        budget_model_name: str | None = None,
    ) -> None:
        """结算：在 Redis 中累加真实 cost/token；DB 由 rollup 任务异步同步"""
        client = await get_redis_client()
        seg = _redis_model_segment(budget_model_name)
        key = _bucket_key(target_kind, target_id, period, model_segment=seg)
        pipe = client.pipeline()
        pipe.hincrbyfloat(key, "cost", float(delta_cost))
        pipe.hincrby(key, "tokens", delta_tokens)
        if period == PERIOD_DAILY:
            pipe.expire(key, 90000)
        elif period == PERIOD_MONTHLY:
            pipe.expire(key, 86400 * 35)
        await pipe.execute()


__all__ = [
    "PERIOD_DAILY",
    "PERIOD_MONTHLY",
    "PERIOD_TOTAL",
    "BudgetCheckResult",
    "BudgetService",
    "BudgetUsageCoord",
    "ScopeIdentifier",
    "redis_model_segment_for_budget",
]
