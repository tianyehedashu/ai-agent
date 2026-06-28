"""QuotaPlanService - 通用滚动窗口配额算子（Redis）

服务于上下游对称的配额体系（上游 ``provider_quotas`` 扁平规则 / 下游 ``EntitlementPlan``）：

- 键空间 ``gateway:quota:{ns}:{plan_id}:{quota_id}``，``ns ∈ {entitlement, provider}``
  保证两侧不串扰；与 ``BudgetService`` (``gateway:budget:*``) 与 ``RateLimit``
  (``gateway:rate:*``) 也互相独立。
- 每条 quota 内部使用「分钟分桶」：每分钟一条 ``…:b:{minute}`` hash，所有分钟通过
  ``…:idx`` ZSET 索引；查询用量时 ``ZREMRANGEBYSCORE`` 清窗口外，``ZRANGE`` +
  ``HMGET`` 累加得到当前窗口 used。``window_seconds=0`` 表示「整套餐期累计」。

服务自身不接 ORM，也不做读缓存：用量是强一致计数，缓存语义不安全；配置层缓存由
上游 ``provider_quota_config_cache`` / 下游 ``entitlement_config_cache`` 负责。
所有 ``PlanQuotaSpec`` 由调用方仓储查得。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from domains.gateway.domain.quota.quota_plan import (
    ExhaustedReason,
    PlanQuotaSnapshot,
    PlanQuotaSpec,
    QuotaPlanCheckResult,
    QuotaPlanNamespace,
    QuotaPlanReservation,
    compute_minute_index,
    compute_reset_at,
    compute_window_start_minute,
)
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)


def _quota_key_base(ns: QuotaPlanNamespace, plan_id: uuid.UUID, quota_id: uuid.UUID) -> str:
    return f"gateway:quota:{ns}:{plan_id}:{quota_id}"


def _bucket_key(base: str, minute_unix: int) -> str:
    return f"{base}:b:{minute_unix}"


def _index_key(base: str) -> str:
    return f"{base}:idx"


def _bucket_ttl_seconds(spec: PlanQuotaSpec) -> int:
    """单个分钟桶 TTL：窗口长度 + 120s 容差。

    - rolling：``window_seconds + 120``。
    - calendar_daily_utc：1 天 + 容差。
    - calendar_monthly_utc：31 天 + 容差。
    - ``window_seconds=0``（整套餐期）：90 天兜底。
    """
    if spec.window_seconds <= 0:
        return 86400 * 90
    strategy = spec.reset_strategy
    if strategy == "calendar_daily_utc":
        return 86400 + 120
    if strategy == "calendar_monthly_utc":
        return 86400 * 31 + 120
    return spec.window_seconds + 120


# 原子预扣硬计数维度（requests + images）：窗口内对所有分钟桶求和后判定 limit，通过才写入当前分钟桶。
# 单脚本单往返、无显式锁，消除「读快照→判断→写预扣」之间的 TOCTOU 超额放行。
# token/usd 维度允许一定漂移，仍由 check_and_reserve 的 snapshot 预检负责，不在此处强一致。
# 注：脚本经 base 派生 bucket key（未在 KEYS 声明），与 _compute_snapshot 的多键 pipeline
# 读取同源，依赖单实例 Redis（本部署为单实例阿里云 Redis，非 Cluster）。
#
# 返回值：
#   {1, used_requests, used_images}              成功
#   {0, used_requests, used_images}              requests 超限
#   {2, used_requests, used_images}              images 超限
_RESERVE_HARD_LUA_SCRIPT = """
local ikey = KEYS[1]
local base = ARGV[1]
local current_minute = ARGV[2]
local window_start_minute = tonumber(ARGV[3])
local request_count = tonumber(ARGV[4])
local image_count = tonumber(ARGV[5])
local limit_requests = tonumber(ARGV[6])
local limit_images = tonumber(ARGV[7])
local bucket_ttl = tonumber(ARGV[8])
local index_ttl = tonumber(ARGV[9])

if window_start_minute >= 0 then
    redis.call('zremrangebyscore', ikey, 0, window_start_minute - 1)
end

local used_requests = 0
local used_images = 0
local minutes = redis.call('zrange', ikey, 0, -1)
for i = 1, #minutes do
    local vals = redis.call('hmget', base .. ':b:' .. minutes[i], 'requests', 'images')
    if vals[1] then
        used_requests = used_requests + tonumber(vals[1])
    end
    if vals[2] then
        used_images = used_images + tonumber(vals[2])
    end
end

if limit_requests > 0 and used_requests + request_count > limit_requests then
    return {0, used_requests, used_images}
end

if limit_images > 0 and used_images + image_count > limit_images then
    return {2, used_requests, used_images}
end

local bkey = base .. ':b:' .. current_minute
if request_count > 0 then
    redis.call('hincrby', bkey, 'requests', request_count)
end
if image_count > 0 then
    redis.call('hincrby', bkey, 'images', image_count)
end
redis.call('zadd', ikey, tonumber(current_minute), current_minute)
redis.call('expire', bkey, bucket_ttl)
redis.call('expire', ikey, index_ttl)
return {1, used_requests, used_images}
"""


# release 回滚硬计数维度并钳制下限为 0，避免分钟桶被减成负值（双重 release / 桶过期重建）
# 导致后续窗口求和偏低、变相放行。
_RELEASE_HARD_LUA_SCRIPT = """
local key = KEYS[1]
local decr_requests = tonumber(ARGV[1])
local decr_images = tonumber(ARGV[2])

if decr_requests > 0 then
    local rv = redis.call('hincrby', key, 'requests', -decr_requests)
    if rv < 0 then
        redis.call('hset', key, 'requests', 0)
    end
end

if decr_images > 0 then
    local iv = redis.call('hincrby', key, 'images', -decr_images)
    if iv < 0 then
        redis.call('hset', key, 'images', 0)
    end
end

return {redis.call('hget', key, 'requests') or 0, redis.call('hget', key, 'images') or 0}
"""


class QuotaPlanService:
    """通用 Plan 配额管理 - 上下游共用。"""

    # ------------------------------------------------------------------
    # check_and_reserve
    # ------------------------------------------------------------------
    async def check_and_reserve(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        specs: list[PlanQuotaSpec],
        *,
        estimate_tokens: int = 0,
        estimate_usd: Decimal = Decimal("0"),
        request_count: int = 1,
        image_count: int = 0,
        now: datetime | None = None,
    ) -> QuotaPlanCheckResult:
        """读取所有 quotas 的当前用量，任一耗尽则整体拒绝；否则按单请求预扣。

        预扣只增加 requests = ``request_count`` / images = ``image_count``；
        token / cost 在 ``commit`` 阶段按真实用量结算（与 BudgetService 同形态，
        避免 estimate 与真实偏离时双账）。
        """
        if not specs:
            return QuotaPlanCheckResult(allowed=True)
        when = now or datetime.now(UTC)
        snapshots = await self.snapshot(ns, plan_id, specs, now=when)
        for snap in snapshots:
            spec = snap.spec
            # 检查 estimate 是否会让该桶超限（仅 requests/images 维度精确，
            # token/usd 在 commit 时再校验；这里给出 ``estimate_tokens`` 边界保护）
            limit_usd = spec.limit_usd
            limit_tokens = spec.limit_tokens
            limit_requests = spec.limit_requests
            limit_images = spec.limit_images
            if limit_usd is not None and 0 < limit_usd <= snap.used_usd + estimate_usd:
                return QuotaPlanCheckResult(
                    allowed=False,
                    snapshots=snapshots,
                    exhausted_snapshot=PlanQuotaSnapshot(
                        spec=spec,
                        used_usd=snap.used_usd,
                        used_tokens=snap.used_tokens,
                        used_requests=snap.used_requests,
                        used_images=snap.used_images,
                        exhausted_reason="usd",
                        earliest_minute_in_window=snap.earliest_minute_in_window,
                    ),
                )
            if limit_tokens is not None and 0 < limit_tokens <= snap.used_tokens + estimate_tokens:
                return QuotaPlanCheckResult(
                    allowed=False,
                    snapshots=snapshots,
                    exhausted_snapshot=PlanQuotaSnapshot(
                        spec=spec,
                        used_usd=snap.used_usd,
                        used_tokens=snap.used_tokens,
                        used_requests=snap.used_requests,
                        used_images=snap.used_images,
                        exhausted_reason="tokens",
                        earliest_minute_in_window=snap.earliest_minute_in_window,
                    ),
                )
            if (
                limit_requests is not None
                and 0 < limit_requests < snap.used_requests + request_count
            ):
                return QuotaPlanCheckResult(
                    allowed=False,
                    snapshots=snapshots,
                    exhausted_snapshot=PlanQuotaSnapshot(
                        spec=spec,
                        used_usd=snap.used_usd,
                        used_tokens=snap.used_tokens,
                        used_requests=snap.used_requests,
                        used_images=snap.used_images,
                        exhausted_reason="requests",
                        earliest_minute_in_window=snap.earliest_minute_in_window,
                    ),
                )
            if limit_images is not None and 0 < limit_images < snap.used_images + image_count:
                return QuotaPlanCheckResult(
                    allowed=False,
                    snapshots=snapshots,
                    exhausted_snapshot=PlanQuotaSnapshot(
                        spec=spec,
                        used_usd=snap.used_usd,
                        used_tokens=snap.used_tokens,
                        used_requests=snap.used_requests,
                        used_images=snap.used_images,
                        exhausted_reason="images",
                        earliest_minute_in_window=snap.earliest_minute_in_window,
                    ),
                )

        # 逐 spec 原子预扣硬计数维度（requests + images）：Lua 在窗口求和后判定 limit 并写当前分钟桶，
        # 关闭并发下「快照预检通过 → 写入」之间的超额窗口。token/usd 仍由上方预检兜底（可容忍漂移）。
        minute_unix = compute_minute_index(when)
        client = await get_redis_client()
        reservations: list[QuotaPlanReservation] = []
        try:
            for spec in specs:
                base = _quota_key_base(ns, plan_id, spec.quota_id)
                ikey = _index_key(base)
                if spec.window_seconds and spec.window_seconds > 0:
                    window_start_minute = compute_window_start_minute(
                        when,
                        spec.window_seconds,
                        strategy=spec.reset_strategy,
                        row_valid_from=None,
                        period_reset_anchor=spec.period_reset_anchor,
                    )
                else:
                    window_start_minute = -1
                ttl = _bucket_ttl_seconds(spec)
                limit_requests = (
                    spec.limit_requests if spec.limit_requests and spec.limit_requests > 0 else 0
                )
                limit_images = (
                    spec.limit_images if spec.limit_images and spec.limit_images > 0 else 0
                )
                result = await client.eval(
                    _RESERVE_HARD_LUA_SCRIPT,
                    1,
                    ikey,
                    base,
                    str(minute_unix),
                    str(int(window_start_minute)),
                    str(int(request_count)),
                    str(int(image_count)),
                    str(int(limit_requests)),
                    str(int(limit_images)),
                    str(int(ttl)),
                    str(int(ttl)),
                )
                status = int(result[0])
                if status != 1:
                    # 并发下原子拒绝：回滚已预扣项，返回耗尽快照（重算以填齐 reset 锚点）
                    for r in reservations:
                        await self._release_one(ns, plan_id, r)
                    exhausted = await self._compute_snapshot(ns, plan_id, spec, when)
                    reason: ExhaustedReason = "images" if status == 2 else "requests"
                    return QuotaPlanCheckResult(
                        allowed=False,
                        snapshots=snapshots,
                        exhausted_snapshot=PlanQuotaSnapshot(
                            spec=spec,
                            used_usd=exhausted.used_usd,
                            used_tokens=exhausted.used_tokens,
                            used_requests=exhausted.used_requests,
                            used_images=exhausted.used_images,
                            exhausted_reason=reason,
                            earliest_minute_in_window=exhausted.earliest_minute_in_window,
                        ),
                    )
                reservations.append(
                    QuotaPlanReservation(
                        plan_id=plan_id,
                        spec=spec,
                        minute_unix=minute_unix,
                        reserved_requests=request_count,
                        reserved_images=image_count,
                    )
                )
        except Exception:
            # 任何预扣失败 → 回滚已预扣项，避免计数漂移
            for r in reservations:
                await self._release_one(ns, plan_id, r)
            raise
        return QuotaPlanCheckResult(allowed=True, snapshots=snapshots, reservations=reservations)

    # ------------------------------------------------------------------
    # commit
    # ------------------------------------------------------------------
    async def commit(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        specs: list[PlanQuotaSpec],
        *,
        delta_tokens: int,
        delta_usd: Decimal,
        delta_requests: int = 0,
        delta_images: int = 0,
        now: datetime | None = None,
    ) -> None:
        """请求成功后累加真实 cost / tokens（不再增 requests/images，因为 reserve 已加）。

        ``delta_images`` 用于 reserve 阶段预估张数与响应真实张数差额的校正（多扣负值、少扣正值）。
        """
        if not specs:
            return
        when = now or datetime.now(UTC)
        minute_unix = compute_minute_index(when)
        client = await get_redis_client()
        for spec in specs:
            base = _quota_key_base(ns, plan_id, spec.quota_id)
            bkey = _bucket_key(base, minute_unix)
            ikey = _index_key(base)
            pipe = client.pipeline()
            if delta_tokens:
                pipe.hincrby(bkey, "tokens", delta_tokens)
            if delta_usd:
                pipe.hincrbyfloat(bkey, "cost", float(delta_usd))
            if delta_requests:
                pipe.hincrby(bkey, "requests", delta_requests)
            if delta_images:
                pipe.hincrby(bkey, "images", delta_images)
            pipe.zadd(ikey, {str(minute_unix): minute_unix})
            ttl = _bucket_ttl_seconds(spec)
            pipe.expire(bkey, ttl)
            pipe.expire(ikey, ttl)
            await pipe.execute()

    # ------------------------------------------------------------------
    # release
    # ------------------------------------------------------------------
    async def release(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        reservations: list[QuotaPlanReservation],
    ) -> None:
        for r in reservations:
            await self._release_one(ns, plan_id, r)

    async def _release_one(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        reservation: QuotaPlanReservation,
    ) -> None:
        client = await get_redis_client()
        base = _quota_key_base(ns, plan_id, reservation.spec.quota_id)
        bkey = _bucket_key(base, reservation.minute_unix)
        try:
            await client.eval(
                _RELEASE_HARD_LUA_SCRIPT,
                1,
                bkey,
                str(int(reservation.reserved_requests)),
                str(int(reservation.reserved_images)),
            )
        except Exception as exc:  # pragma: no cover - 不影响主路径
            logger.warning("QuotaPlanService.release failed for %s: %s", bkey, exc)

    # ------------------------------------------------------------------
    # set_window_usage - 管理面手工校正（与 PG bucket 对齐）
    # ------------------------------------------------------------------
    async def set_window_usage(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        spec: PlanQuotaSpec,
        *,
        cost_usd: Decimal,
        tokens: int,
        requests: int,
        images: int = 0,
        now: datetime | None = None,
    ) -> None:
        """将当前窗口累计用量设为绝对值（清空窗口内旧分钟桶，写入当前分钟桶）。"""
        when = now or datetime.now(UTC)
        minute_unix = compute_minute_index(when)
        client = await get_redis_client()
        base = _quota_key_base(ns, plan_id, spec.quota_id)
        ikey = _index_key(base)
        bkey = _bucket_key(base, minute_unix)

        if spec.window_seconds and spec.window_seconds > 0:
            window_start_minute = compute_window_start_minute(
                when,
                spec.window_seconds,
                strategy=spec.reset_strategy,
                row_valid_from=None,
                period_reset_anchor=spec.period_reset_anchor,
            )
            await client.zremrangebyscore(ikey, 0, window_start_minute - 1)

        members_raw = await client.zrange(ikey, 0, -1, withscores=False)
        pipe = client.pipeline()
        for raw in members_raw:
            try:
                minute = int(raw.decode() if isinstance(raw, bytes) else raw)
            except (ValueError, AttributeError):
                continue
            pipe.delete(_bucket_key(base, minute))
        pipe.delete(f"{base}:forced_until")
        pipe.delete(ikey)
        pipe.hset(
            bkey,
            mapping={
                "cost": str(cost_usd),
                "tokens": str(tokens),
                "requests": str(requests),
                "images": str(images),
            },
        )
        pipe.zadd(ikey, {str(minute_unix): minute_unix})
        ttl = _bucket_ttl_seconds(spec)
        pipe.expire(bkey, ttl)
        pipe.expire(ikey, ttl)
        await pipe.execute()

    # ------------------------------------------------------------------
    # force_exhaust - 上游 429 / insufficient_quota 信号反馈
    # ------------------------------------------------------------------
    async def force_exhaust(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        specs: list[PlanQuotaSpec],
        *,
        until: datetime | None = None,
        reason: str = "upstream_quota_exhausted",
        now: datetime | None = None,
    ) -> None:
        """把指定 plan 的所有 quota 桶立刻打满到 ``limit``，模拟"已耗尽"。

        触发场景：上游返回 429/402/RESOURCE_EXHAUSTED，本地预测 vs 上游真实计数偏差。
        实现：在当前分钟桶补齐 ``limit_*`` 累计差额；同时设置 ``::forced_until`` 标记
        作为快照层兜底（超过 until 时再恢复正常滚动）。

        - ``until``：解禁时刻（None 表示按 ``compute_reset_at`` 自然策略）。
        - 不抛错；失败仅记 warn 日志，避免影响主路径。
        """
        if not specs:
            return
        when = now or datetime.now(UTC)
        minute_unix = compute_minute_index(when)
        client = await get_redis_client()
        for spec in specs:
            try:
                snap = await self._compute_snapshot(ns, plan_id, spec, when)
                base = _quota_key_base(ns, plan_id, spec.quota_id)
                bkey = _bucket_key(base, minute_unix)
                ikey = _index_key(base)

                pipe = client.pipeline()
                if spec.limit_requests is not None and spec.limit_requests > 0:
                    delta = max(spec.limit_requests - snap.used_requests, 0)
                    if delta:
                        pipe.hincrby(bkey, "requests", delta)
                if spec.limit_tokens is not None and spec.limit_tokens > 0:
                    delta_t = max(spec.limit_tokens - snap.used_tokens, 0)
                    if delta_t:
                        pipe.hincrby(bkey, "tokens", delta_t)
                if spec.limit_usd is not None and spec.limit_usd > 0:
                    delta_u = max(float(spec.limit_usd - snap.used_usd), 0.0)
                    if delta_u > 0:
                        pipe.hincrbyfloat(bkey, "cost", delta_u)
                if spec.limit_images is not None and spec.limit_images > 0:
                    delta_i = max(spec.limit_images - snap.used_images, 0)
                    if delta_i:
                        pipe.hincrby(bkey, "images", delta_i)
                pipe.zadd(ikey, {str(minute_unix): minute_unix})
                ttl = _bucket_ttl_seconds(spec)
                pipe.expire(bkey, ttl)
                pipe.expire(ikey, ttl)

                # 标记强制耗尽：到 until/或自然 reset 之前所有 snapshot 都视为耗尽
                resolved_until = until or compute_reset_at(
                    strategy=spec.reset_strategy,
                    window_seconds=spec.window_seconds,
                    now=when,
                    earliest_minute_in_window=snap.earliest_minute_in_window,
                    row_valid_from=None,
                )
                if resolved_until is not None:
                    forced_key = f"{base}:forced_until"
                    pipe.set(
                        forced_key,
                        str(int(resolved_until.timestamp())),
                        ex=max(int((resolved_until - when).total_seconds()) + 60, 60),
                    )
                await pipe.execute()
                logger.info(
                    "QuotaPlanService.force_exhaust ns=%s plan=%s quota=%s reason=%s until=%s",
                    ns,
                    plan_id,
                    spec.quota_id,
                    reason,
                    resolved_until.isoformat() if resolved_until else "natural",
                )
            except Exception as exc:  # pragma: no cover - 不影响主路径
                logger.warning(
                    "QuotaPlanService.force_exhaust failed for plan=%s quota=%s: %s",
                    plan_id,
                    spec.quota_id,
                    exc,
                )

    # ------------------------------------------------------------------
    # snapshot
    # ------------------------------------------------------------------
    async def snapshot(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        specs: list[PlanQuotaSpec],
        *,
        now: datetime | None = None,
    ) -> list[PlanQuotaSnapshot]:
        when = now or datetime.now(UTC)
        return [await self._compute_snapshot(ns, plan_id, spec, when) for spec in specs]

    async def _compute_snapshot(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        spec: PlanQuotaSpec,
        now: datetime,
    ) -> PlanQuotaSnapshot:
        client = await get_redis_client()
        base = _quota_key_base(ns, plan_id, spec.quota_id)
        ikey = _index_key(base)

        forced_exhausted = False
        try:
            forced_raw = await client.get(f"{base}:forced_until")
            if forced_raw is not None:
                forced_until_ts = int(
                    forced_raw.decode() if isinstance(forced_raw, bytes) else forced_raw
                )
                if forced_until_ts > int(now.timestamp()):
                    forced_exhausted = True
        except Exception as exc:  # pragma: no cover
            logger.warning("force_exhaust flag read failed for %s: %s", base, exc)

        if spec.window_seconds and spec.window_seconds > 0:
            window_start_minute = compute_window_start_minute(
                now,
                spec.window_seconds,
                strategy=spec.reset_strategy,
                row_valid_from=None,
                period_reset_anchor=spec.period_reset_anchor,
            )
            try:
                await client.zremrangebyscore(ikey, 0, window_start_minute - 1)
            except Exception as exc:  # pragma: no cover
                logger.warning("zremrangebyscore failed for %s: %s", ikey, exc)
            members = await client.zrange(ikey, 0, -1, withscores=False)
        else:
            members = await client.zrange(ikey, 0, -1, withscores=False)

        minutes: list[int] = []
        for raw in members:
            try:
                minute = int(raw.decode() if isinstance(raw, bytes) else raw)
            except (ValueError, AttributeError):
                continue
            minutes.append(minute)

        used_cost = Decimal("0")
        used_tokens = 0
        used_requests = 0
        used_images = 0
        if minutes:
            pipe = client.pipeline()
            for m in minutes:
                pipe.hmget(_bucket_key(base, m), ["cost", "tokens", "requests", "images"])
            rows = await pipe.execute()
            for row in rows:
                if not row:
                    continue
                c, t, r, im = row
                if c:
                    used_cost += Decimal(c.decode() if isinstance(c, bytes) else str(c))
                if t:
                    used_tokens += int(t.decode() if isinstance(t, bytes) else t)
                if r:
                    used_requests += int(r.decode() if isinstance(r, bytes) else r)
                if im:
                    used_images += int(im.decode() if isinstance(im, bytes) else im)

        exhausted_reason = None
        if spec.limit_usd is not None and spec.limit_usd > 0 and used_cost >= spec.limit_usd:
            exhausted_reason = "usd"
        elif (
            spec.limit_tokens is not None
            and spec.limit_tokens > 0
            and used_tokens >= spec.limit_tokens
        ):
            exhausted_reason = "tokens"
        elif (
            spec.limit_requests is not None
            and spec.limit_requests > 0
            and used_requests >= spec.limit_requests
        ):
            exhausted_reason = "requests"
        elif (
            spec.limit_images is not None
            and spec.limit_images > 0
            and used_images >= spec.limit_images
        ):
            exhausted_reason = "images"
        elif forced_exhausted:
            exhausted_reason = (
                "requests"
                if spec.limit_requests
                else "images"
                if spec.limit_images
                else "tokens"
                if spec.limit_tokens
                else "usd"
            )

        return PlanQuotaSnapshot(
            spec=spec,
            used_usd=used_cost,
            used_tokens=used_tokens,
            used_requests=used_requests,
            used_images=used_images,
            exhausted_reason=exhausted_reason,
            earliest_minute_in_window=min(minutes) if minutes else None,
        )


_quota_plan_service_singleton: QuotaPlanService | None = None


def get_quota_plan_service() -> QuotaPlanService:
    global _quota_plan_service_singleton
    if _quota_plan_service_singleton is None:
        _quota_plan_service_singleton = QuotaPlanService()
    return _quota_plan_service_singleton


__all__ = [
    "QuotaPlanService",
    "get_quota_plan_service",
]
