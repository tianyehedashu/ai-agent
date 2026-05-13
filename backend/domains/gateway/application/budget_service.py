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


def _bucket_key(scope: str, scope_id: str | None, period: str) -> str:
    """Redis key for budget current values"""
    sid = scope_id or "system"
    if period == PERIOD_DAILY:
        suffix = datetime.now(UTC).strftime("%Y%m%d")
    elif period == PERIOD_MONTHLY:
        suffix = datetime.now(UTC).strftime("%Y%m")
    else:
        suffix = "total"
    return f"gateway:budget:{scope}:{sid}:{period}:{suffix}"


def _rate_key(scope: str, scope_id: str | None, dimension: str) -> str:
    """Redis key for rpm/tpm windows (60 秒滚动桶)"""
    sid = scope_id or "system"
    return f"gateway:rate:{scope}:{sid}:{dimension}"


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
        scope: str,
        scope_id: str | None,
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
            key = _rate_key(scope, scope_id, "rpm")
            await client.zremrangebyscore(key, 0, window_start)
            count = await client.zcard(key)
            if count >= rpm_limit:
                raise RateLimitExceededError(scope=f"{scope}:rpm", retry_after=60)
            await client.zadd(key, {f"{now}:{uuid.uuid4()}": now})
            await client.expire(key, 90)

        if tpm_limit and tpm_limit > 0 and estimate_tokens > 0:
            key = _rate_key(scope, scope_id, "tpm")
            await client.zremrangebyscore(key, 0, window_start)
            # 累加目前窗口内 token 数（成员名形如 "<tokens>:<uuid>"）
            current_tokens = 0
            members = await client.zrange(key, 0, -1, withscores=True)
            for member, _score in members:
                try:
                    payload = (
                        member.decode() if isinstance(member, bytes) else str(member)
                    )
                    parts = payload.split(":", 1)
                    if len(parts) == 2:
                        current_tokens += int(parts[0])
                except (ValueError, AttributeError):
                    continue
            if current_tokens + estimate_tokens > tpm_limit:
                raise RateLimitExceededError(scope=f"{scope}:tpm", retry_after=60)
            await client.zadd(
                key, {f"{estimate_tokens}:{uuid.uuid4()}": now}
            )
            await client.expire(key, 90)

    # ---------------------------------------------------------------------
    # 预算预扣 / 结算
    # ---------------------------------------------------------------------

    async def check_budget(
        self,
        *,
        scope: str,
        scope_id: str | None,
        period: str,
        limit_usd: Decimal | None,
        limit_tokens: int | None,
        limit_requests: int | None,
    ) -> BudgetCheckResult:
        """读取当前 budget 状态；超限返回 allowed=False

        当前 cost/tokens/requests 来自 Redis 桶，由 commit 异步累加。
        """
        client = await get_redis_client()
        key = _bucket_key(scope, scope_id, period)
        values = await client.hmget(key, ["cost", "tokens", "requests"])
        used_cost = Decimal(values[0].decode() if values[0] else "0")
        used_tokens = int(values[1].decode() if values[1] else "0")
        used_requests = int(values[2].decode() if values[2] else "0")

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
        scope: str,
        scope_id: str | None,
        period: str,
        limit_requests: int | None,
    ) -> None:
        """预扣 1 个请求名额（用于防止并发请求穿透）

        若 limit_requests 已达，抛 BudgetExceededError。
        """
        if limit_requests is None or limit_requests <= 0:
            return
        client = await get_redis_client()
        key = _bucket_key(scope, scope_id, period)
        new_value = await client.hincrby(key, "requests", 1)
        # 设置 TTL：daily 1 天，monthly 1 个月，total 不过期
        if period == PERIOD_DAILY:
            await client.expire(key, 90000)
        elif period == PERIOD_MONTHLY:
            await client.expire(key, 86400 * 35)
        if new_value > limit_requests:
            # 回滚
            await client.hincrby(key, "requests", -1)
            raise BudgetExceededError(
                scope=scope,
                period=period,
                limit=float(limit_requests),
                used=float(new_value - 1),
            )

    async def commit(
        self,
        *,
        scope: str,
        scope_id: str | None,
        period: str,
        delta_cost: Decimal,
        delta_tokens: int,
    ) -> None:
        """结算：在 Redis 中累加真实 cost/token；DB 由 rollup 任务异步同步"""
        client = await get_redis_client()
        key = _bucket_key(scope, scope_id, period)
        pipe = client.pipeline()
        pipe.hincrbyfloat(key, "cost", float(delta_cost))
        pipe.hincrby(key, "tokens", delta_tokens)
        if period == PERIOD_DAILY:
            pipe.expire(key, 90000)
        elif period == PERIOD_MONTHLY:
            pipe.expire(key, 86400 * 35)
        await pipe.execute()

    async def release(
        self,
        *,
        scope: str,
        scope_id: str | None,
        period: str,
    ) -> None:
        """请求失败时回滚预扣的请求数"""
        client = await get_redis_client()
        key = _bucket_key(scope, scope_id, period)
        await client.hincrby(key, "requests", -1)


__all__ = [
    "PERIOD_DAILY",
    "PERIOD_MONTHLY",
    "PERIOD_TOTAL",
    "BudgetCheckResult",
    "BudgetService",
    "ScopeIdentifier",
]
