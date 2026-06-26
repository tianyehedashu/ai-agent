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
from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    compute_platform_redis_period_suffix,
)
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)


PERIOD_DAILY = "daily"
PERIOD_MONTHLY = "monthly"
PERIOD_TOTAL = "total"

_RESERVE_LUA_SCRIPT = """
local key = KEYS[1]
local incr_requests = tonumber(ARGV[1])
local incr_tokens = tonumber(ARGV[2])
local limit_requests = tonumber(ARGV[3])
local limit_tokens = tonumber(ARGV[4])
local expire_seconds = tonumber(ARGV[5])
local incr_images = tonumber(ARGV[6])
local limit_images = tonumber(ARGV[7])

local requests_val = 0
if incr_requests > 0 then
    requests_val = redis.call('HINCRBY', key, 'requests', 1)
    if expire_seconds > 0 then
        redis.call('EXPIRE', key, expire_seconds)
    end
    if limit_requests > 0 and requests_val > limit_requests then
        redis.call('HINCRBY', key, 'requests', -1)
        return {-1, requests_val}
    end
end

if incr_tokens > 0 then
    local tokens_val = redis.call('HINCRBY', key, 'tokens', incr_tokens)
    if expire_seconds > 0 then
        redis.call('EXPIRE', key, expire_seconds)
    end
    if limit_tokens > 0 and tokens_val > limit_tokens then
        if incr_requests > 0 then
            redis.call('HINCRBY', key, 'requests', -1)
        end
        redis.call('HINCRBY', key, 'tokens', -incr_tokens)
        return {0, tokens_val}
    end
end

if incr_images > 0 then
    local images_val = redis.call('HINCRBY', key, 'images', incr_images)
    if expire_seconds > 0 then
        redis.call('EXPIRE', key, expire_seconds)
    end
    if limit_images > 0 and images_val > limit_images then
        if incr_requests > 0 then
            redis.call('HINCRBY', key, 'requests', -1)
        end
        if incr_tokens > 0 then
            redis.call('HINCRBY', key, 'tokens', -incr_tokens)
        end
        redis.call('HINCRBY', key, 'images', -incr_images)
        return {2, images_val}
    end
end
return {1, 0}
"""

_RATE_LIMIT_RPM_LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local rpm_limit = tonumber(ARGV[3])
local expire_seconds = tonumber(ARGV[4])

redis.call('zremrangebyscore', key, 0, window_start)
local count = redis.call('zcard', key)
if count >= rpm_limit then
    return {-1, count}
end
redis.call('zadd', key, now, now .. ':' .. redis.call('incr', 'gateway:rate:seq'))
redis.call('expire', key, expire_seconds)
return {1, count}
"""

_RATE_LIMIT_TPM_LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local tpm_limit = tonumber(ARGV[3])
local estimate_tokens = tonumber(ARGV[4])
local expire_seconds = tonumber(ARGV[5])

redis.call('zremrangebyscore', key, 0, window_start)
local members = redis.call('zrange', key, 0, -1)
local current_tokens = 0
for i = 1, #members do
    local payload = members[i]
    local colon_pos = string.find(payload, ':')
    if colon_pos then
        local token_str = string.sub(payload, 1, colon_pos - 1)
        local tokens = tonumber(token_str)
        if tokens then
            current_tokens = current_tokens + tokens
        end
    end
end
if current_tokens + estimate_tokens > tpm_limit then
    return {0, current_tokens}
end
redis.call('zadd', key, now, estimate_tokens .. ':' .. redis.call('incr', 'gateway:rate:seq'))
redis.call('expire', key, expire_seconds)
return {1, current_tokens}
"""


def _model_segment_hash(model_name: str) -> str:
    return hashlib.sha256(model_name.encode("utf-8")).hexdigest()[:16]


def _redis_model_segment(budget_model_name: str | None) -> str | None:
    if budget_model_name is None:
        return None
    return _model_segment_hash(budget_model_name)


def redis_model_segment_for_budget(budget_model_name: str | None) -> str | None:
    return _redis_model_segment(budget_model_name)


def _redis_credential_segment(credential_id: uuid.UUID | str | None) -> str | None:
    if credential_id is None:
        return None
    return _model_segment_hash(str(credential_id))


def redis_credential_segment_for_budget(
    credential_id: uuid.UUID | str | None,
) -> str | None:
    return _redis_credential_segment(credential_id)


def redis_tenant_segment_for_budget(tenant_id: uuid.UUID | str | None) -> str | None:
    """成员总量/模型护栏按团队隔离时的 Redis 桶分段（仅 user 维度使用）。"""
    if tenant_id is None:
        return None
    return _model_segment_hash(str(tenant_id))


def _bucket_key(
    target_kind: str,
    target_id: str | None,
    period: str,
    *,
    model_segment: str | None = None,
    credential_segment: str | None = None,
    tenant_segment: str | None = None,
    period_reset_anchor: PeriodResetAnchor | None = None,
    now: datetime | None = None,
) -> str:
    """Redis key for budget current values"""
    sid = target_id or "system"
    when = now or datetime.now(UTC)
    suffix = compute_platform_redis_period_suffix(
        when,
        period,
        period_reset_anchor or DEFAULT_PERIOD_RESET_ANCHOR,
    )
    base = f"gateway:budget:{target_kind}:{sid}:{period}:{suffix}"
    if tenant_segment:
        base = f"{base}:t:{tenant_segment}"
    if credential_segment:
        base = f"{base}:c:{credential_segment}"
    if model_segment:
        return f"{base}:m:{model_segment}"
    return base


def _legacy_team_bucket_key(
    target_kind: str,
    target_id: str | None,
    period: str,
    *,
    model_segment: str | None = None,
    credential_segment: str | None = None,
    tenant_segment: str | None = None,
    period_reset_anchor: PeriodResetAnchor | None = None,
    now: datetime | None = None,
) -> str | None:
    """迁移期：``tenant`` 预算曾以 ``team`` 写入 Redis，读时合并旧 key。"""
    if target_kind != "tenant":
        return None
    return _bucket_key(
        "team",
        target_id,
        period,
        model_segment=model_segment,
        credential_segment=credential_segment,
        tenant_segment=tenant_segment,
        period_reset_anchor=period_reset_anchor,
        now=now,
    )


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
    credential_segment: str | None = None
    tenant_segment: str | None = None
    period_reset_anchor: PeriodResetAnchor = DEFAULT_PERIOD_RESET_ANCHOR


@dataclass
class BudgetCheckResult:
    """预扣结果"""

    allowed: bool
    reason: str | None = None
    used_usd: Decimal = Decimal("0")
    used_tokens: int = 0
    used_requests: int = 0
    used_images: int = 0


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

        采用 60s 滚动窗口（Redis Sorted Set），rpm/tpm 均通过 Lua 脚本原子化执行，
        避免多步命令之间的竞态条件与 Python 端 O(N) 遍历。
        """
        if not (rpm_limit and rpm_limit > 0) and not (tpm_limit and tpm_limit > 0):
            return

        client = await get_redis_client()
        now = datetime.now(UTC).timestamp()
        window_start = now - 60
        expire_seconds = 90

        if rpm_limit and rpm_limit > 0:
            rpm_key = _rate_key(target_kind, target_id, "rpm")
            rpm_result = await client.eval(
                _RATE_LIMIT_RPM_LUA_SCRIPT,
                1,
                rpm_key,
                now,
                window_start,
                int(rpm_limit),
                expire_seconds,
            )
            status = int(rpm_result[0])
            if status == -1:
                raise RateLimitExceededError(
                    scope=f"{target_kind}:rpm",
                    retry_after=60,
                )

        if tpm_limit and tpm_limit > 0 and estimate_tokens > 0:
            tpm_key = _rate_key(target_kind, target_id, "tpm")
            tpm_result = await client.eval(
                _RATE_LIMIT_TPM_LUA_SCRIPT,
                1,
                tpm_key,
                now,
                window_start,
                int(tpm_limit),
                int(estimate_tokens),
                expire_seconds,
            )
            status = int(tpm_result[0])
            if status == 0:
                raise RateLimitExceededError(
                    scope=f"{target_kind}:tpm",
                    retry_after=60,
                )

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
        credential_segment: str | None = None,
        tenant_segment: str | None = None,
        period_reset_anchor: PeriodResetAnchor | None = None,
    ) -> tuple[Decimal, int, int, int]:
        coord = BudgetUsageCoord(
            target_kind=target_kind,
            target_id=target_id,
            period=period,
            model_segment=model_segment,
            credential_segment=credential_segment,
            tenant_segment=tenant_segment,
            period_reset_anchor=period_reset_anchor or DEFAULT_PERIOD_RESET_ANCHOR,
        )
        batch = await self.read_budget_usage_batch([coord])
        return batch.get(coord, (Decimal("0"), 0, 0, 0))

    async def read_budget_usage_batch(
        self,
        coords: list[BudgetUsageCoord],
    ) -> dict[BudgetUsageCoord, tuple[Decimal, int, int, int]]:
        """Pipeline 批量读取预算 Redis 桶（含 tenant→team 迁移期 legacy key）。

        返回 ``(used_cost, used_tokens, used_requests, used_images)`` 4-tuple。
        """
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
                credential_segment=coord.credential_segment,
                tenant_segment=coord.tenant_segment,
                period_reset_anchor=coord.period_reset_anchor,
            )
            key_entries.append((coord, primary, False))
            legacy = _legacy_team_bucket_key(
                coord.target_kind,
                coord.target_id,
                coord.period,
                model_segment=coord.model_segment,
                credential_segment=coord.credential_segment,
                tenant_segment=coord.tenant_segment,
                period_reset_anchor=coord.period_reset_anchor,
            )
            if legacy is not None:
                key_entries.append((coord, legacy, True))

        pipe = client.pipeline()
        for _coord, key, _is_legacy in key_entries:
            pipe.hmget(key, ["cost", "tokens", "requests", "images"])
        raw_results = await pipe.execute()

        out: dict[BudgetUsageCoord, tuple[Decimal, int, int, int]] = {
            c: (Decimal("0"), 0, 0, 0) for c in unique_coords
        }
        for (coord, _key, _is_legacy), values in zip(key_entries, raw_results, strict=True):
            used_cost, used_tokens, used_requests, used_images = out[coord]
            cost_raw = values[0]
            tokens_raw = values[1]
            requests_raw = values[2]
            images_raw = values[3]
            # ``tenant`` Redis keys used to be written as ``team``. During the
            # migration window a single budget period can legitimately have
            # usage in both keys, so the effective usage is their sum.
            used_cost += Decimal(cost_raw.decode() if cost_raw else "0")
            used_tokens += int(tokens_raw.decode() if tokens_raw else "0")
            used_requests += int(requests_raw.decode() if requests_raw else "0")
            used_images += int(images_raw.decode() if images_raw else "0")
            out[coord] = (used_cost, used_tokens, used_requests, used_images)
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
        credential_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        prefetched_usage: tuple[Decimal, int, int, int] | None = None,
        limit_images: int | None = None,
        period_reset_anchor: PeriodResetAnchor | None = None,
    ) -> BudgetCheckResult:
        """读取当前 budget 状态；超限返回 allowed=False

        当前 cost/tokens/requests/images 来自 Redis 桶，由 commit 异步累加。
        """
        seg = _redis_model_segment(budget_model_name)
        cred_seg = _redis_credential_segment(credential_id)
        tenant_seg = redis_tenant_segment_for_budget(tenant_id)
        anchor = period_reset_anchor or DEFAULT_PERIOD_RESET_ANCHOR
        if prefetched_usage is not None:
            used_cost, used_tokens, used_requests, used_images = prefetched_usage
        else:
            used_cost, used_tokens, used_requests, used_images = await self._read_budget_usage(
                target_kind=target_kind,
                target_id=target_id,
                period=period,
                model_segment=seg,
                credential_segment=cred_seg,
                tenant_segment=tenant_seg,
                period_reset_anchor=anchor,
            )

        if limit_usd is not None and 0 < limit_usd <= used_cost:
            return BudgetCheckResult(
                allowed=False,
                reason="usd",
                used_usd=used_cost,
                used_tokens=used_tokens,
                used_requests=used_requests,
                used_images=used_images,
            )
        if limit_tokens and 0 < limit_tokens <= used_tokens:
            return BudgetCheckResult(
                allowed=False,
                reason="tokens",
                used_usd=used_cost,
                used_tokens=used_tokens,
                used_requests=used_requests,
                used_images=used_images,
            )
        if limit_requests and 0 < limit_requests <= used_requests:
            return BudgetCheckResult(
                allowed=False,
                reason="requests",
                used_usd=used_cost,
                used_tokens=used_tokens,
                used_requests=used_requests,
                used_images=used_images,
            )
        if limit_images and 0 < limit_images <= used_images:
            return BudgetCheckResult(
                allowed=False,
                reason="images",
                used_usd=used_cost,
                used_tokens=used_tokens,
                used_requests=used_requests,
                used_images=used_images,
            )
        return BudgetCheckResult(
            allowed=True,
            used_usd=used_cost,
            used_tokens=used_tokens,
            used_requests=used_requests,
            used_images=used_images,
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
        credential_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        limit_images: int | None = None,
        image_count: int = 0,
        period_reset_anchor: PeriodResetAnchor | None = None,
    ) -> tuple[int, int, int]:
        """预扣请求名额 / token 估算 / 图片张数（Lua 原子化，防止并发穿透）。

        返回 ``(reserved_requests, reserved_tokens, reserved_images)``。
        """
        reserve_requests = limit_requests is not None and limit_requests > 0
        reserve_tokens = limit_tokens is not None and limit_tokens > 0 and estimate_tokens > 0
        reserve_images = limit_images is not None and limit_images > 0 and image_count > 0
        if not reserve_requests and not reserve_tokens and not reserve_images:
            return (0, 0, 0)

        client = await get_redis_client()
        seg = _redis_model_segment(budget_model_name)
        cred_seg = _redis_credential_segment(credential_id)
        tenant_seg = redis_tenant_segment_for_budget(tenant_id)
        key = _bucket_key(
            target_kind,
            target_id,
            period,
            model_segment=seg,
            credential_segment=cred_seg,
            tenant_segment=tenant_seg,
            period_reset_anchor=period_reset_anchor,
        )
        expire = (
            90000 if period == PERIOD_DAILY else (86400 * 35 if period == PERIOD_MONTHLY else 0)
        )
        do_incr_requests = 1 if reserve_requests else 0

        result = await client.eval(
            _RESERVE_LUA_SCRIPT,
            1,
            key,
            do_incr_requests,
            int(estimate_tokens if reserve_tokens else 0),
            int(limit_requests or 0),
            int(limit_tokens or 0),
            int(expire),
            int(image_count if reserve_images else 0),
            int(limit_images or 0),
        )
        assert isinstance(result, (list, tuple)) and len(result) >= 1
        status = int(result[0])

        if status == -1:
            raise BudgetExceededError(
                scope=target_kind,
                period=period,
                limit=float(limit_requests or 0),
                used=float(result[1]) - 1,
            )
        if status == 0:
            raise BudgetExceededError(
                scope=target_kind,
                period=period,
                limit=float(limit_tokens or 0),
                used=float(result[1]) - estimate_tokens,
            )
        if status == 2:
            raise BudgetExceededError(
                scope=target_kind,
                period=period,
                limit=float(limit_images or 0),
                used=float(result[1]) - image_count,
            )
        # status == 1: success
        reserved_requests = 1 if reserve_requests else 0
        reserved_tokens = estimate_tokens if reserve_tokens else 0
        reserved_images = image_count if reserve_images else 0
        return (reserved_requests, reserved_tokens, reserved_images)

    async def release(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        budget_model_name: str | None = None,
        credential_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        reserved_requests: int = 1,
        reserved_tokens: int = 0,
        reserved_images: int = 0,
        period_reset_anchor: PeriodResetAnchor | None = None,
    ) -> None:
        """请求失败时回滚预扣的请求数 / token 估算 / 图片张数。"""
        if reserved_requests <= 0 and reserved_tokens <= 0 and reserved_images <= 0:
            return
        client = await get_redis_client()
        seg = _redis_model_segment(budget_model_name)
        cred_seg = _redis_credential_segment(credential_id)
        tenant_seg = redis_tenant_segment_for_budget(tenant_id)
        key = _bucket_key(
            target_kind,
            target_id,
            period,
            model_segment=seg,
            credential_segment=cred_seg,
            tenant_segment=tenant_seg,
            period_reset_anchor=period_reset_anchor,
        )
        if reserved_requests > 0:
            await client.hincrby(key, "requests", -reserved_requests)
        if reserved_tokens > 0:
            await client.hincrby(key, "tokens", -reserved_tokens)
        if reserved_images > 0:
            await client.hincrby(key, "images", -reserved_images)

    async def commit(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        delta_cost: Decimal,
        delta_tokens: int,
        budget_model_name: str | None = None,
        credential_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        delta_images: int = 0,
        period_reset_anchor: PeriodResetAnchor | None = None,
    ) -> None:
        """结算：在 Redis 中累加真实 cost/token/images；DB 由 rollup 任务异步同步"""
        client = await get_redis_client()
        seg = _redis_model_segment(budget_model_name)
        cred_seg = _redis_credential_segment(credential_id)
        tenant_seg = redis_tenant_segment_for_budget(tenant_id)
        key = _bucket_key(
            target_kind,
            target_id,
            period,
            model_segment=seg,
            credential_segment=cred_seg,
            tenant_segment=tenant_seg,
            period_reset_anchor=period_reset_anchor,
        )
        pipe = client.pipeline()
        pipe.hincrbyfloat(key, "cost", float(delta_cost))
        pipe.hincrby(key, "tokens", delta_tokens)
        if delta_images:
            pipe.hincrby(key, "images", delta_images)
        if period == PERIOD_DAILY:
            pipe.expire(key, 90000)
        elif period == PERIOD_MONTHLY:
            pipe.expire(key, 86400 * 35)
        await pipe.execute()

    async def set_budget_usage(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        cost: Decimal,
        tokens: int,
        requests: int,
        budget_model_name: str | None = None,
        credential_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        images: int = 0,
        period_reset_anchor: PeriodResetAnchor | None = None,
    ) -> None:
        """管理面：将 Redis 预算桶设为绝对用量（与 commit 累加相对）。"""
        client = await get_redis_client()
        seg = _redis_model_segment(budget_model_name)
        cred_seg = _redis_credential_segment(credential_id)
        tenant_seg = redis_tenant_segment_for_budget(tenant_id)
        key = _bucket_key(
            target_kind,
            target_id,
            period,
            model_segment=seg,
            credential_segment=cred_seg,
            tenant_segment=tenant_seg,
            period_reset_anchor=period_reset_anchor,
        )
        pipe = client.pipeline()
        pipe.hset(
            key,
            mapping={
                "cost": str(cost),
                "tokens": str(tokens),
                "requests": str(requests),
                "images": str(images),
            },
        )
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
    "redis_credential_segment_for_budget",
    "redis_model_segment_for_budget",
    "redis_tenant_segment_for_budget",
]
