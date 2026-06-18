"""QuotaPlanService 与上下游 Guard 行为测试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, cast
from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application import entitlement_guard as entitlement_guard_module
from domains.gateway.application import provider_quota_guard as provider_quota_guard_module
from domains.gateway.application import quota_plan_service as quota_plan_service_module
from domains.gateway.application.entitlement_config_cache import (
    clear_entitlement_config_cache_for_tests,
)
from domains.gateway.application.entitlement_guard import (
    EntitlementContext,
    EntitlementGuard,
)
from domains.gateway.application.provider_quota_config_cache import (
    clear_provider_quota_config_cache_for_tests,
)
from domains.gateway.application.provider_quota_guard import ProviderQuotaGuard
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

    def hset(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("hset", args, kwargs))

    def delete(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("delete", args, kwargs))

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

    def hset(self, key: str, mapping: dict[str, str] | None = None, **kwargs: Any) -> int:
        _ = kwargs
        if mapping is None:
            return 0
        row = self.hashes.setdefault(key, {})
        row.update(mapping)
        return len(mapping)

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.hashes:
                del self.hashes[key]
                removed += 1
            if key in self.zsets:
                del self.zsets[key]
                removed += 1
            if key in self.values:
                del self.values[key]
                removed += 1
        return removed

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
async def test_quota_plan_service_set_window_usage_replaces_window_totals(
    fake_redis: _FakeRedis,
) -> None:
    _ = fake_redis
    service = QuotaPlanService()
    plan_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="daily",
        window_seconds=86400,
        limit_tokens=10_000,
        limit_requests=100,
        limit_usd=Decimal("50"),
    )
    start = datetime(2026, 5, 18, 3, 0, tzinfo=UTC)
    await service.check_and_reserve(PROVIDER_NS, plan_id, [spec], now=start)
    await service.commit(
        PROVIDER_NS,
        plan_id,
        [spec],
        delta_tokens=500,
        delta_usd=Decimal("1.00"),
        now=start,
    )

    await service.set_window_usage(
        PROVIDER_NS,
        plan_id,
        spec,
        cost_usd=Decimal("9.50"),
        tokens=2000,
        requests=7,
        now=start,
    )

    snap = (await service.snapshot(PROVIDER_NS, plan_id, [spec], now=start))[0]
    assert snap.used_usd == Decimal("9.50")
    assert snap.used_tokens == 2000
    assert snap.used_requests == 7
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
    created_at: datetime = datetime(2026, 1, 1, tzinfo=UTC)


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
    reset_timezone: str = "UTC"
    reset_time_minutes: int = 0
    reset_day_of_month: int = 1
    enabled: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None


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

    async def list_with_quotas_for_scope(
        self, *_args: object, **_kwargs: object
    ) -> list[tuple[_FakeEntitlementPlan, list[_FakeEntitlementQuota]]]:
        return [(self.plan, list(self.quotas))] if self.plan is not None else []


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
    clear_entitlement_config_cache_for_tests()
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
    clear_entitlement_config_cache_for_tests()
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
class _FakeProviderQuotaRow:
    id: uuid.UUID
    credential_id: uuid.UUID
    real_model: str | None
    label: str
    window_seconds: int
    limit_usd: Decimal | None = None
    limit_tokens: int | None = None
    limit_requests: int | None = None
    reset_strategy: str = "rolling"
    reset_timezone: str = "UTC"
    reset_time_minutes: int = 0
    reset_day_of_month: int = 1
    enabled: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class _FakeSessionCM:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeProviderRepo:
    rules: ClassVar[list[_FakeProviderQuotaRow]] = []

    def __init__(self, _session: object) -> None:
        pass

    async def list_active_for_credential_model(
        self, *_args: object, **_kwargs: object
    ) -> list[_FakeProviderQuotaRow]:
        return self.rules

    async def get(self, rule_id: uuid.UUID) -> _FakeProviderQuotaRow | None:
        return next((r for r in self.rules if r.id == rule_id), None)


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
async def test_provider_quota_guard_exhaustion_raises_router_cooldown_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_provider_quota_config_cache_for_tests()
    now = datetime(2026, 5, 18, tzinfo=UTC)
    rule_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    _FakeProviderRepo.rules = [
        _FakeProviderQuotaRow(
            id=rule_id,
            credential_id=cred_id,
            real_model="openai/gpt-4o-mini",
            label="daily",
            window_seconds=86400,
            limit_requests=1,
        )
    ]
    monkeypatch.setattr(provider_quota_guard_module, "ProviderQuotaRepository", _FakeProviderRepo)
    monkeypatch.setattr(provider_quota_guard_module, "get_session_context", lambda: _FakeSessionCM())

    guard = ProviderQuotaGuard(quota_service=cast("QuotaPlanService", _ExhaustedQuota()))
    with pytest.raises(ProviderPlanExhaustedError) as exc_info:
        await guard.check_and_reserve(
            credential_id=cred_id,
            real_model="openai/gpt-4o-mini",
            now=now,
        )

    assert exc_info.value.plan_id == str(rule_id)
    assert exc_info.value.cooldown_seconds == 86400


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_quota_guard_mark_upstream_exhausted_forces_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_provider_quota_config_cache_for_tests()
    rule_id = uuid.uuid4()
    second_rule_id = uuid.uuid4()
    _FakeProviderRepo.rules = [
        _FakeProviderQuotaRow(
            id=rule_id,
            credential_id=uuid.uuid4(),
            real_model=None,
            label="daily",
            window_seconds=86400,
            limit_requests=100,
            reset_strategy="calendar_daily_utc",
        ),
        _FakeProviderQuotaRow(
            id=second_rule_id,
            credential_id=uuid.uuid4(),
            real_model="ep-1",
            label="model-daily",
            window_seconds=86400,
            limit_requests=50,
            reset_strategy="calendar_daily_utc",
        ),
    ]
    monkeypatch.setattr(provider_quota_guard_module, "ProviderQuotaRepository", _FakeProviderRepo)
    monkeypatch.setattr(provider_quota_guard_module, "get_session_context", lambda: _FakeSessionCM())
    quota = _RecordingProviderQuota()

    guard = ProviderQuotaGuard(quota_service=cast("QuotaPlanService", quota))
    await guard.mark_upstream_exhausted_rules(
        [rule_id, second_rule_id],
        reason="upstream_signal:RateLimitError",
    )

    assert len(quota.forced) == 2
    forced_ids = {item[1] for item in quota.forced}
    assert forced_ids == {rule_id, second_rule_id}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_quota_guard_skips_db_on_config_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_provider_quota_config_cache_for_tests()
    now = datetime(2026, 5, 18, tzinfo=UTC)
    rule_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    _FakeProviderRepo.rules = [
        _FakeProviderQuotaRow(
            id=rule_id,
            credential_id=cred_id,
            real_model="openai/gpt-4o-mini",
            label="daily",
            window_seconds=86400,
            limit_requests=10,
        )
    ]
    monkeypatch.setattr(provider_quota_guard_module, "ProviderQuotaRepository", _FakeProviderRepo)
    session_entries = 0

    class _CountingSessionCM:
        async def __aenter__(self) -> object:
            nonlocal session_entries
            session_entries += 1
            return object()

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        provider_quota_guard_module,
        "get_session_context",
        lambda: _CountingSessionCM(),
    )
    monkeypatch.setattr(
        "domains.gateway.application.provider_quota_config_cache._get_version",
        AsyncMock(return_value="11"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.provider_quota_config_cache._get_redis_client",
        AsyncMock(return_value=None),
    )

    guard = ProviderQuotaGuard(quota_service=cast("QuotaPlanService", _AllowedQuota()))
    first = await guard.check_and_reserve(
        credential_id=cred_id,
        real_model="openai/gpt-4o-mini",
        now=now,
    )
    second = await guard.check_and_reserve(
        credential_id=cred_id,
        real_model="openai/gpt-4o-mini",
        now=now,
    )

    assert session_entries == 1
    assert first[0].rule_id == rule_id
    assert second[0].rule_id == rule_id


@pytest.mark.unit
def test_quota_plan_service_has_no_internal_lru_cache() -> None:
    """简化缓存层级：确认 QuotaPlanService 不再持有进程内 LRU 缓存。"""
    from domains.gateway.application.quota_plan_service import QuotaPlanService

    assert not hasattr(QuotaPlanService, "_snapshot_cache")
    # 同时确认旧缓存相关方法已移除
    for method in ("_cache_bucket", "_cache_get", "_cache_put", "_invalidate_cache"):
        assert not hasattr(QuotaPlanService, method), f"遗留缓存方法: {method}"
