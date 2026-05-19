"""QuotaPlanService - 通用滚动窗口配额算子（Redis）

服务于上下游对称的 Plan 体系（``ProviderPlan`` / ``EntitlementPlan``）：

- 键空间 ``gateway:quota:{ns}:{plan_id}:{quota_id}``，``ns ∈ {entitlement, provider}``
  保证两侧不串扰；与 ``BudgetService`` (``gateway:budget:*``) 与 ``RateLimit``
  (``gateway:rate:*``) 也互相独立。
- 每条 quota 内部使用「分钟分桶」：每分钟一条 ``…:b:{minute}`` hash，所有分钟通过
  ``…:idx`` ZSET 索引；查询用量时 ``ZREMRANGEBYSCORE`` 清窗口外，``ZRANGE`` +
  ``HMGET`` 累加得到当前窗口 used。``window_seconds=0`` 表示「整套餐期累计」。
- 30s 进程内 LRU 读缓存，缓存 key 含 ``minute_unix // (30/60)`` 取整以让缓存自然失效。

服务自身不接 ORM。所有 ``PlanQuotaSpec`` 由调用方仓储查得。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import time
import uuid

from domains.gateway.domain.quota_plan import (
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


SNAPSHOT_CACHE_TTL_SECONDS = 30


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
    - plan_anniversary：``window_seconds + 120``。
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


@dataclass
class _SnapshotCacheEntry:
    snapshot: PlanQuotaSnapshot
    expires_at: float


class QuotaPlanService:
    """通用 Plan 配额管理 - 上下游共用。"""

    def __init__(self) -> None:
        # key: (ns, plan_id, quota_id, minute_unix_30s_bucket)
        self._snapshot_cache: dict[tuple[str, uuid.UUID, uuid.UUID, int], _SnapshotCacheEntry] = {}

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
        now: datetime | None = None,
    ) -> QuotaPlanCheckResult:
        """读取所有 quotas 的当前用量，任一耗尽则整体拒绝；否则按单请求预扣。

        预扣只增加 requests = ``request_count``；token / cost 在 ``commit`` 阶段
        按真实用量结算（与 BudgetService 同形态，避免 estimate 与真实偏离时双账）。
        """
        if not specs:
            return QuotaPlanCheckResult(allowed=True)
        when = now or datetime.now(UTC)
        snapshots = await self.snapshot(ns, plan_id, specs, now=when)
        for snap in snapshots:
            spec = snap.spec
            # 检查 estimate 是否会让该桶超限（仅 request_count 维度精确，
            # token/usd 在 commit 时再校验；这里给出 ``estimate_tokens`` 边界保护）
            limit_usd = spec.limit_usd
            limit_tokens = spec.limit_tokens
            limit_requests = spec.limit_requests
            if (
                limit_usd is not None
                and limit_usd > 0
                and snap.used_usd + estimate_usd >= limit_usd
            ):
                return QuotaPlanCheckResult(
                    allowed=False,
                    snapshots=snapshots,
                    exhausted_snapshot=PlanQuotaSnapshot(
                        spec=spec,
                        used_usd=snap.used_usd,
                        used_tokens=snap.used_tokens,
                        used_requests=snap.used_requests,
                        exhausted_reason="usd",
                        earliest_minute_in_window=snap.earliest_minute_in_window,
                    ),
                )
            if (
                limit_tokens is not None
                and limit_tokens > 0
                and snap.used_tokens + estimate_tokens >= limit_tokens
            ):
                return QuotaPlanCheckResult(
                    allowed=False,
                    snapshots=snapshots,
                    exhausted_snapshot=PlanQuotaSnapshot(
                        spec=spec,
                        used_usd=snap.used_usd,
                        used_tokens=snap.used_tokens,
                        used_requests=snap.used_requests,
                        exhausted_reason="tokens",
                        earliest_minute_in_window=snap.earliest_minute_in_window,
                    ),
                )
            if (
                limit_requests is not None
                and limit_requests > 0
                and snap.used_requests + request_count > limit_requests
            ):
                return QuotaPlanCheckResult(
                    allowed=False,
                    snapshots=snapshots,
                    exhausted_snapshot=PlanQuotaSnapshot(
                        spec=spec,
                        used_usd=snap.used_usd,
                        used_tokens=snap.used_tokens,
                        used_requests=snap.used_requests,
                        exhausted_reason="requests",
                        earliest_minute_in_window=snap.earliest_minute_in_window,
                    ),
                )

        # 通过：对每个 spec 同时预扣 request_count 到当前分钟桶
        minute_unix = compute_minute_index(when)
        client = await get_redis_client()
        reservations: list[QuotaPlanReservation] = []
        try:
            for spec in specs:
                base = _quota_key_base(ns, plan_id, spec.quota_id)
                bkey = _bucket_key(base, minute_unix)
                ikey = _index_key(base)
                pipe = client.pipeline()
                pipe.hincrby(bkey, "requests", request_count)
                pipe.zadd(ikey, {str(minute_unix): minute_unix})
                ttl = _bucket_ttl_seconds(spec)
                pipe.expire(bkey, ttl)
                pipe.expire(ikey, ttl)
                await pipe.execute()
                reservations.append(
                    QuotaPlanReservation(
                        plan_id=plan_id,
                        spec=spec,
                        minute_unix=minute_unix,
                        reserved_requests=request_count,
                    )
                )
        except Exception:
            # 任何预扣失败 → 回滚已预扣项，避免计数漂移
            for r in reservations:
                await self._release_one(ns, plan_id, r)
            raise
        # 失效缓存以避免读到旧用量（commit/release 同样处理）
        self._invalidate_cache(ns, plan_id, [s.quota_id for s in specs])
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
        now: datetime | None = None,
    ) -> None:
        """请求成功后累加真实 cost / tokens（不再增 requests，因为 reserve 已加）。"""
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
            pipe.zadd(ikey, {str(minute_unix): minute_unix})
            ttl = _bucket_ttl_seconds(spec)
            pipe.expire(bkey, ttl)
            pipe.expire(ikey, ttl)
            await pipe.execute()
        self._invalidate_cache(ns, plan_id, [s.quota_id for s in specs])

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
        self._invalidate_cache(ns, plan_id, [r.spec.quota_id for r in reservations])

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
            await client.hincrby(bkey, "requests", -reservation.reserved_requests)
        except Exception as exc:  # pragma: no cover - 不影响主路径
            logger.warning("QuotaPlanService.release failed for %s: %s", bkey, exc)

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
                    plan_valid_from=spec.plan_valid_from,
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
        self._invalidate_cache(ns, plan_id, [s.quota_id for s in specs])

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
        results: list[PlanQuotaSnapshot] = []
        for spec in specs:
            cached = self._cache_get(ns, plan_id, spec, when)
            if cached is not None:
                results.append(cached)
                continue
            snap = await self._compute_snapshot(ns, plan_id, spec, when)
            self._cache_put(ns, plan_id, spec, when, snap)
            results.append(snap)
        return results

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
                plan_valid_from=spec.plan_valid_from,
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
        if minutes:
            pipe = client.pipeline()
            for m in minutes:
                pipe.hmget(_bucket_key(base, m), ["cost", "tokens", "requests"])
            rows = await pipe.execute()
            for row in rows:
                if not row:
                    continue
                c, t, r = row
                if c:
                    used_cost += Decimal(c.decode() if isinstance(c, bytes) else str(c))
                if t:
                    used_tokens += int(t.decode() if isinstance(t, bytes) else t)
                if r:
                    used_requests += int(r.decode() if isinstance(r, bytes) else r)

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
        elif forced_exhausted:
            exhausted_reason = (
                "requests" if spec.limit_requests else "tokens" if spec.limit_tokens else "usd"
            )

        return PlanQuotaSnapshot(
            spec=spec,
            used_usd=used_cost,
            used_tokens=used_tokens,
            used_requests=used_requests,
            exhausted_reason=exhausted_reason,
            earliest_minute_in_window=min(minutes) if minutes else None,
        )

    # ------------------------------------------------------------------
    # 进程内缓存（30s）
    # ------------------------------------------------------------------
    def _cache_bucket(self, when: datetime) -> int:
        # 30 秒一格
        return int(when.timestamp() // SNAPSHOT_CACHE_TTL_SECONDS)

    def _cache_get(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        spec: PlanQuotaSpec,
        when: datetime,
    ) -> PlanQuotaSnapshot | None:
        key = (ns, plan_id, spec.quota_id, self._cache_bucket(when))
        entry = self._snapshot_cache.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._snapshot_cache.pop(key, None)
            return None
        return entry.snapshot

    def _cache_put(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        spec: PlanQuotaSpec,
        when: datetime,
        snap: PlanQuotaSnapshot,
    ) -> None:
        key = (ns, plan_id, spec.quota_id, self._cache_bucket(when))
        self._snapshot_cache[key] = _SnapshotCacheEntry(
            snapshot=snap,
            expires_at=time.time() + SNAPSHOT_CACHE_TTL_SECONDS,
        )
        # 简单清理过期条目
        if len(self._snapshot_cache) > 4096:
            now_ts = time.time()
            stale = [k for k, v in self._snapshot_cache.items() if v.expires_at < now_ts]
            for k in stale:
                self._snapshot_cache.pop(k, None)

    def _invalidate_cache(
        self,
        ns: QuotaPlanNamespace,
        plan_id: uuid.UUID,
        quota_ids: list[uuid.UUID],
    ) -> None:
        for qid in quota_ids:
            for key in list(self._snapshot_cache.keys()):
                if key[0] == ns and key[1] == plan_id and key[2] == qid:
                    self._snapshot_cache.pop(key, None)


_quota_plan_service_singleton: QuotaPlanService | None = None


def get_quota_plan_service() -> QuotaPlanService:
    global _quota_plan_service_singleton
    if _quota_plan_service_singleton is None:
        _quota_plan_service_singleton = QuotaPlanService()
    return _quota_plan_service_singleton


__all__ = [
    "SNAPSHOT_CACHE_TTL_SECONDS",
    "QuotaPlanService",
    "get_quota_plan_service",
]
