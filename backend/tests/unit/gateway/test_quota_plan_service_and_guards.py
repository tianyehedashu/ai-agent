"""QuotaPlanService 与上下游 Guard 行为测试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, cast
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application import entitlement_guard as entitlement_guard_module
from domains.gateway.application import provider_plan_guard as provider_plan_guard_module
from domains.gateway.application import quota_plan_service as quota_plan_service_module
from domains.gateway.application.entitlement_guard import (
    EntitlementContext,
    EntitlementGuard,
)
from domains.gateway.application.provider_plan_guard import ProviderPlanGuard
from domains.gateway.application.quota_plan_service import QuotaPlanService
from domains.gateway.domain.errors import (
    EntitlementPlanExhaustedError,
    ProviderPlanExhaustedError,
)
from domains.gateway.domain.quota_plan import (
    PROVIDER_NS,
    PlanQuotaSnapshot,
    PlanQuotaSpec,
    QuotaPlanCheckResult,
    QuotaPlanReservation,
)


class _FakeRedisPipeline:
    def __init__(self, client: _FakeRedis) -> None:
        self._client = client
        self._ops: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def hincrby(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("hincrby", args, kwargs))

    def hincrbyfloat(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("hincrbyfloat", args, kwargs))

    def zadd(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("zadd", args, kwargs))

    def expire(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("expire", args, kwargs))

    def hmget(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("hmget", args, kwargs))

    def set(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("set", args, kwargs))

    async def execute(self) -> list[Any]:
        out: list[Any] = []
        for name, args, kwargs in self._ops:
            result = getattr(self._client, name)(*args, **kwargs)
            out.append(result)
        self._ops.clear()
        return out


class _FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.values: dict[str, str] = {}

    def pipeline(self) -> _FakeRedisPipeline:
        return _FakeRedisPipeline(self)

    def hincrby(self, key: str, field: str, amount: int) -> int:
        row = self.hashes.setdefault(key, {})
        row[field] = str(int(row.get(field, "0")) + amount)
        return int(row[field])

    def hincrbyfloat(self, key: str, field: str, amount: float) -> float:
        row = self.hashes.setdefault(key, {})
        row[field] = str(float(row.get(field, "0")) + amount)
        return float(row[field])

    def zadd(self, key: str, mapping: dict[str, int | float]) -> int:
        zset = self.zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if member not in zset:
                added += 1
            zset[member] = float(score)
        return added

    def expire(self, _key: str, _ttl: int) -> bool:
        return True

    def hmget(self, key: str, fields: list[str]) -> list[str | None]:
        row = self.hashes.get(key, {})
        return [row.get(field) for field in fields]

    def set(self, key: str, value: str, *, ex: int | None = None) -> bool:
        _ = ex
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def zrange(
        self, key: str, _start: int, _end: int, *, withscores: bool = False
    ) -> list[Any]:
        items = sorted(self.zsets.get(key, {}).items(), key=lambda item: item[1])
        if withscores:
            return items
        return [member for member, _score in items]

    async def zremrangebyscore(self, key: str, min_score: int, max_score: int) -> int:
        zset = self.zsets.setdefault(key, {})
        doomed = [
            member
            for member, score in zset.items()
            if float(min_score) <= score <= float(max_score)
        ]
        for member in doomed:
            zset.pop(member, None)
        return len(doomed)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    client = _FakeRedis()

    async def get_client() -> _FakeRedis:
        return client

    monkeypatch.setattr(quota_plan_service_module, "get_redis_client", get_client)
    return client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_quota_plan_service_reserve_commit_release_and_exhaustion(
    fake_redis: _FakeRedis,
) -> None:
    _ = fake_redis
    service = QuotaPlanService()
    plan_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="minute",
        window_seconds=60,
        limit_requests=1,
        limit_tokens=100,
        limit_usd=Decimal("1.00"),
    )
    now = datetime(2026, 5, 18, 3, 0, tzinfo=UTC)

    first = await service.check_and_reserve(PROVIDER_NS, plan_id, [spec], now=now)
    assert first.allowed
    assert len(first.reservations) == 1

    await service.commit(
        PROVIDER_NS,
        plan_id,
        [spec],
        delta_tokens=12,
        delta_usd=Decimal("0.25"),
        now=now,
    )
    snap = (await service.snapshot(PROVIDER_NS, plan_id, [spec], now=now))[0]
    assert snap.used_requests == 1
    assert snap.used_tokens == 12
    assert snap.used_usd == Decimal("0.25")

    second = await service.check_and_reserve(PROVIDER_NS, plan_id, [spec], now=now)
    assert not second.allowed
    assert second.exhausted_snapshot is not None
    assert second.exhausted_snapshot.exhausted_reason == "requests"

    await service.release(PROVIDER_NS, plan_id, first.reservations)
    after_release = await service.check_and_reserve(PROVIDER_NS, plan_id, [spec], now=now)
    assert after_release.allowed


@pytest.mark.unit
@pytest.mark.asyncio
async def test_quota_plan_service_rolling_window_prunes_old_buckets(
    fake_redis: _FakeRedis,
) -> None:
    _ = fake_redis
    service = QuotaPlanService()
    plan_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="rolling-minute",
        window_seconds=60,
        limit_requests=10,
    )
    start = datetime(2026, 5, 18, 3, 0, tzinfo=UTC)
    later = start + timedelta(seconds=121)

    result = await service.check_and_reserve(PROVIDER_NS, plan_id, [spec], now=start)
    assert result.allowed

    snap = (await service.snapshot(PROVIDER_NS, plan_id, [spec], now=later))[0]
    assert snap.used_requests == 0
    assert not snap.exhausted


@pytest.mark.unit
@pytest.mark.asyncio
async def test_quota_plan_service_force_exhaust_marks_provider_plan_exhausted(
    fake_redis: _FakeRedis,
) -> None:
    _ = fake_redis
    service = QuotaPlanService()
    plan_id = uuid.uuid4()
    now = datetime(2026, 5, 18, 3, 0, tzinfo=UTC)
    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="daily",
        window_seconds=86400,
        limit_requests=100,
        reset_strategy="calendar_daily_utc",
    )

    await service.force_exhaust(PROVIDER_NS, plan_id, [spec], now=now)

    snap = (await service.snapshot(PROVIDER_NS, plan_id, [spec], now=now))[0]
    assert snap.exhausted
    assert snap.exhausted_reason == "requests"
    assert snap.reset_at(now) == datetime(2026, 5, 19, tzinfo=UTC)


@dataclass
class _FakeEntitlementPlan:
    id: uuid.UUID
    label: str
    valid_from: datetime
    valid_until: datetime
    is_active: bool = True
    included_models: list[str] | None = None
    included_capabilities: list[str] | None = None


@dataclass
class _FakeEntitlementQuota:
    id: uuid.UUID
    label: str
    window_seconds: int
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None
    unit_price_usd_per_token: Decimal | None = None
    unit_price_usd_per_request: Decimal | None = None
    reset_strategy: str = "rolling"


class _FakeEntitlementRepo:
    plan: _FakeEntitlementPlan | None = None
    quotas: ClassVar[list[_FakeEntitlementQuota]] = []

    def __init__(self, _session: object) -> None:
        pass

    async def get_active_for_scope(
        self, *_args: object, **_kwargs: object
    ) -> _FakeEntitlementPlan | None:
        return self.plan

    async def list_quotas(self, _plan_id: uuid.UUID) -> list[_FakeEntitlementQuota]:
        return self.quotas

    async def list_for_scope(self, *_args: object, **_kwargs: object) -> list[_FakeEntitlementPlan]:
        return [self.plan] if self.plan is not None else []


class _AllowedQuota:
    async def check_and_reserve(self, *_args: object, **_kwargs: object) -> QuotaPlanCheckResult:
        spec = PlanQuotaSpec(
            quota_id=uuid.uuid4(),
            label="daily",
            window_seconds=86400,
            limit_requests=10,
        )
        return QuotaPlanCheckResult(
            allowed=True,
            reservations=[
                QuotaPlanReservation(
                    plan_id=uuid.uuid4(),
                    spec=spec,
                    minute_unix=1,
                )
            ],
        )

    async def snapshot(self, *_args: object, **_kwargs: object) -> list[PlanQuotaSnapshot]:
        return []


class _ExhaustedQuota:
    async def check_and_reserve(self, *_args: object, **_kwargs: object) -> QuotaPlanCheckResult:
        spec = PlanQuotaSpec(
            quota_id=uuid.uuid4(),
            label="daily",
            window_seconds=86400,
            limit_requests=1,
        )
        snap = PlanQuotaSnapshot(
            spec=spec,
            used_requests=1,
            exhausted_reason="requests",
            earliest_minute_in_window=1,
        )
        return QuotaPlanCheckResult(allowed=False, exhausted_snapshot=snap)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entitlement_guard_allows_active_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 5, 18, tzinfo=UTC)
    plan_id = uuid.uuid4()
    _FakeEntitlementRepo.plan = _FakeEntitlementPlan(
        id=plan_id,
        label="customer-plan",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )
    _FakeEntitlementRepo.quotas = [
        _FakeEntitlementQuota(
            id=uuid.uuid4(),
            label="daily",
            window_seconds=86400,
            limit_requests=10,
            unit_price_usd_per_request=Decimal("0.01"),
        )
    ]
    monkeypatch.setattr(entitlement_guard_module, "EntitlementPlanRepository", _FakeEntitlementRepo)

    guard = EntitlementGuard(
        cast("AsyncSession", object()),
        quota_service=cast("QuotaPlanService", _AllowedQuota()),
    )
    result = await guard.check_and_reserve(
        EntitlementContext(
            vkey_id=uuid.uuid4(),
            apikey_grant_id=None,
            virtual_model="gpt-4o-mini",
            capability="chat",
        ),
        now=now,
    )

    assert result.plan_id == plan_id
    assert result.plan_label == "customer-plan"
    assert len(result.specs) == 1
    assert result.quota_quotas_unit_prices[_FakeEntitlementRepo.quotas[0].id][1] == Decimal("0.01")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entitlement_guard_exhaustion_is_hard_429_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 5, 18, tzinfo=UTC)
    plan_id = uuid.uuid4()
    _FakeEntitlementRepo.plan = _FakeEntitlementPlan(
        id=plan_id,
        label="customer-plan",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )
    _FakeEntitlementRepo.quotas = [
        _FakeEntitlementQuota(
            id=uuid.uuid4(), label="daily", window_seconds=86400, limit_requests=1
        )
    ]
    monkeypatch.setattr(entitlement_guard_module, "EntitlementPlanRepository", _FakeEntitlementRepo)

    guard = EntitlementGuard(
        cast("AsyncSession", object()),
        quota_service=cast("QuotaPlanService", _ExhaustedQuota()),
    )
    with pytest.raises(EntitlementPlanExhaustedError) as exc_info:
        await guard.check_and_reserve(
            EntitlementContext(
                vkey_id=uuid.uuid4(),
                apikey_grant_id=None,
                virtual_model="gpt-4o-mini",
                capability="chat",
            ),
            now=now,
        )

    assert exc_info.value.plan_id == str(plan_id)
    assert exc_info.value.reason == "requests"


@dataclass
class _FakeProviderPlan:
    id: uuid.UUID
    credential_id: uuid.UUID
    real_model: str | None
    label: str
    valid_from: datetime
    valid_until: datetime
    is_active: bool = True


@dataclass
class _FakeProviderQuota:
    id: uuid.UUID
    label: str
    window_seconds: int
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None
    reset_strategy: str = "rolling"


class _FakeSessionCM:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeProviderRepo:
    plan: _FakeProviderPlan | None = None
    quotas: ClassVar[list[_FakeProviderQuota]] = []

    def __init__(self, _session: object) -> None:
        pass

    async def get_active_for_credential_model(
        self, *_args: object, **_kwargs: object
    ) -> _FakeProviderPlan | None:
        return self.plan

    async def get(self, _plan_id: uuid.UUID) -> _FakeProviderPlan | None:
        return self.plan

    async def list_quotas(self, _plan_id: uuid.UUID) -> list[_FakeProviderQuota]:
        return self.quotas


class _RecordingProviderQuota(_AllowedQuota):
    def __init__(self) -> None:
        self.forced: list[tuple[str, uuid.UUID, list[PlanQuotaSpec], str]] = []

    async def force_exhaust(
        self,
        ns: str,
        plan_id: uuid.UUID,
        specs: list[PlanQuotaSpec],
        *,
        until: datetime | None = None,
        reason: str = "upstream_quota_exhausted",
        now: datetime | None = None,
    ) -> None:
        _ = until
        _ = now
        self.forced.append((ns, plan_id, specs, reason))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_plan_guard_exhaustion_raises_router_cooldown_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 5, 18, tzinfo=UTC)
    _FakeProviderRepo.plan = _FakeProviderPlan(
        id=uuid.uuid4(),
        credential_id=uuid.uuid4(),
        real_model="openai/gpt-4o-mini",
        label="vendor-plan",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )
    _FakeProviderRepo.quotas = [
        _FakeProviderQuota(id=uuid.uuid4(), label="daily", window_seconds=86400, limit_requests=1)
    ]
    monkeypatch.setattr(provider_plan_guard_module, "ProviderPlanRepository", _FakeProviderRepo)
    monkeypatch.setattr(provider_plan_guard_module, "get_session_context", lambda: _FakeSessionCM())

    guard = ProviderPlanGuard(quota_service=cast("QuotaPlanService", _ExhaustedQuota()))
    with pytest.raises(ProviderPlanExhaustedError) as exc_info:
        await guard.check_and_reserve(
            credential_id=_FakeProviderRepo.plan.credential_id,
            real_model="openai/gpt-4o-mini",
            now=now,
        )

    assert exc_info.value.plan_id == str(_FakeProviderRepo.plan.id)
    assert exc_info.value.cooldown_seconds == 86400


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_plan_guard_mark_upstream_exhausted_forces_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 5, 18, tzinfo=UTC)
    plan_id = uuid.uuid4()
    _FakeProviderRepo.plan = _FakeProviderPlan(
        id=plan_id,
        credential_id=uuid.uuid4(),
        real_model=None,
        label="vendor-plan",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )
    _FakeProviderRepo.quotas = [
        _FakeProviderQuota(
            id=uuid.uuid4(),
            label="daily",
            window_seconds=86400,
            limit_requests=100,
            reset_strategy="calendar_daily_utc",
        )
    ]
    monkeypatch.setattr(provider_plan_guard_module, "ProviderPlanRepository", _FakeProviderRepo)
    monkeypatch.setattr(provider_plan_guard_module, "get_session_context", lambda: _FakeSessionCM())
    quota = _RecordingProviderQuota()

    guard = ProviderPlanGuard(quota_service=cast("QuotaPlanService", quota))
    await guard.mark_upstream_exhausted(plan_id, reason="upstream_signal:RateLimitError")

    assert quota.forced
    ns, forced_plan_id, specs, reason = quota.forced[0]
    assert ns == PROVIDER_NS
    assert forced_plan_id == plan_id
    assert specs[0].reset_strategy == "calendar_daily_utc"
    assert reason == "upstream_signal:RateLimitError"


@pytest.mark.unit
def test_quota_plan_service_has_no_internal_lru_cache() -> None:
    """简化缓存层级：确认 QuotaPlanService 不再持有进程内 LRU 缓存。"""
    from domains.gateway.application.quota_plan_service import QuotaPlanService

    assert not hasattr(QuotaPlanService, "_snapshot_cache")
    # 同时确认旧缓存相关方法已移除
    for method in ("_cache_bucket", "_cache_get", "_cache_put", "_invalidate_cache"):
        assert not hasattr(QuotaPlanService, method), f"遗留缓存方法: {method}"
