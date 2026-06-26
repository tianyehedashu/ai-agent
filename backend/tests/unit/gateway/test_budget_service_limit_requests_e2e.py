"""BudgetService ``limit_requests`` 端到端单测。

模拟实际代理调用流程：``check_budget`` → ``reserve``（Lua 原子预扣）→
第二次 ``check_budget`` 拦截 → ``release`` 回滚 → 再次允许。
覆盖 platform / upstream / downstream 三层路径的按次数配额执法。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
import uuid

import pytest

from domains.gateway.application import budget_service as budget_service_module
from domains.gateway.application.budget_service import BudgetService, BudgetUsageCoord
from domains.gateway.domain.errors import BudgetExceededError


class _BudgetFakeRedisPipeline:
    """``budget_service`` 用到的 pipeline 操作子集。

    pipeline 方法同步收集命令，``execute`` 时调用底层同步方法（与 redis-py 一致）。
    """

    def __init__(self, client: _BudgetFakeRedis) -> None:
        self._client = client
        self._ops: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def hincrbyfloat(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("hincrbyfloat_sync", args, kwargs))

    def hincrby(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("hincrby_sync", args, kwargs))

    def expire(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("expire", args, kwargs))

    def hmget(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("hmget_sync", args, kwargs))

    def hset(self, *args: Any, **kwargs: Any) -> None:
        self._ops.append(("hset_sync", args, kwargs))

    async def execute(self) -> list[Any]:
        out: list[Any] = []
        for name, args, kwargs in self._ops:
            out.append(getattr(self._client, name)(*args, **kwargs))
        self._ops.clear()
        return out


class _BudgetFakeRedis:
    """支持 ``_RESERVE_LUA_SCRIPT`` 与 pipeline 的最小 Redis 替身。

    保持与单实例 Redis 同步语义：脚本与 pipeline 操作顺序执行，不让出事件循环。
    底层同步方法以 ``_sync`` 后缀暴露，供 pipeline.execute 复用；
    对外 async 方法对应 redis-py async 客户端接口（``hincrby`` / ``hset`` 等）。
    ``hmget`` 返回 ``bytes`` 以匹配真实 Redis 反序列化路径。
    """

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}

    def pipeline(self) -> _BudgetFakeRedisPipeline:
        return _BudgetFakeRedisPipeline(self)

    # ---- 底层同步方法（pipeline.execute 调用）----
    def hincrby_sync(self, key: str, field: str, amount: int) -> int:
        row = self.hashes.setdefault(key, {})
        value = int(row.get(field, "0")) + amount
        row[field] = str(value)
        return value

    def hincrbyfloat_sync(self, key: str, field: str, amount: float) -> float:
        row = self.hashes.setdefault(key, {})
        value = float(row.get(field, "0")) + amount
        row[field] = str(value)
        return value

    def hmget_sync(self, key: str, fields: list[str]) -> list[bytes | None]:
        row = self.hashes.get(key, {})
        return [row[field].encode() if field in row else None for field in fields]

    def hset_sync(self, key: str, mapping: dict[str, str] | None = None) -> int:
        if mapping is None:
            return 0
        row = self.hashes.setdefault(key, {})
        row.update(mapping)
        return len(mapping)

    def expire(self, _key: str, _ttl: int) -> bool:
        return True

    # ---- 对外 async 方法（直接调用，对应 redis-py async 客户端）----
    async def hincrby(self, key: str, field: str, amount: int) -> int:
        return self.hincrby_sync(key, field, amount)

    async def hset(self, key: str, mapping: dict[str, str] | None = None, **kwargs: Any) -> int:
        return self.hset_sync(key, mapping)

    async def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        keys = list(args[:numkeys])
        argv = list(args[numkeys:])
        if script == budget_service_module._RESERVE_LUA_SCRIPT:
            key = keys[0]
            incr_requests = int(argv[0])
            incr_tokens = int(argv[1])
            limit_requests = int(argv[2])
            limit_tokens = int(argv[3])
            row = self.hashes.setdefault(key, {})

            requests_val = 0
            if incr_requests > 0:
                requests_val = int(row.get("requests", "0")) + 1
                row["requests"] = str(requests_val)
                if limit_requests > 0 and requests_val > limit_requests:
                    row["requests"] = str(int(row["requests"]) - 1)
                    return [-1, requests_val]

            if incr_tokens > 0:
                tokens_val = int(row.get("tokens", "0")) + incr_tokens
                row["tokens"] = str(tokens_val)
                if limit_tokens > 0 and tokens_val > limit_tokens:
                    if incr_requests > 0:
                        row["requests"] = str(int(row["requests"]) - 1)
                    row["tokens"] = str(int(row["tokens"]) - incr_tokens)
                    return [0, tokens_val]
            return [1, 0]

        raise NotImplementedError("BudgetFakeRedis.eval: unsupported script")


@pytest.fixture
def budget_fake_redis(monkeypatch: pytest.MonkeyPatch) -> _BudgetFakeRedis:
    client = _BudgetFakeRedis()

    async def get_client() -> _BudgetFakeRedis:
        return client

    monkeypatch.setattr(budget_service_module, "get_redis_client", get_client)
    return client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_platform_limit_requests_blocks_when_exceeded(
    budget_fake_redis: _BudgetFakeRedis,
) -> None:
    """``limit_requests`` 达上限后第二次 check_budget 必须拒绝。"""
    _ = budget_fake_redis
    service = BudgetService()
    team_id = uuid.uuid4()
    target_id_str = str(team_id)

    first = await service.check_budget(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        limit_usd=None,
        limit_tokens=None,
        limit_requests=1,
    )
    assert first.allowed

    reserved_requests, _reserved_tokens = await service.reserve(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        limit_requests=1,
        limit_tokens=None,
        estimate_tokens=0,
    )
    assert reserved_requests == 1

    second = await service.check_budget(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        limit_usd=None,
        limit_tokens=None,
        limit_requests=1,
    )
    assert not second.allowed
    assert second.reason == "requests"
    assert second.used_requests == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_platform_limit_requests_release_restores_quota(
    budget_fake_redis: _BudgetFakeRedis,
) -> None:
    """release 回滚预扣后，配额应再次可用。"""
    _ = budget_fake_redis
    service = BudgetService()
    team_id = uuid.uuid4()
    target_id_str = str(team_id)

    assert (
        await service.check_budget(
            target_kind="tenant",
            target_id=target_id_str,
            period="daily",
            limit_usd=None,
            limit_tokens=None,
            limit_requests=1,
        )
    ).allowed

    reserved_requests, _ = await service.reserve(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        limit_requests=1,
        limit_tokens=None,
        estimate_tokens=0,
    )
    assert reserved_requests == 1

    await service.release(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        reserved_requests=1,
        reserved_tokens=0,
    )

    assert (
        await service.check_budget(
            target_kind="tenant",
            target_id=target_id_str,
            period="daily",
            limit_usd=None,
            limit_tokens=None,
            limit_requests=1,
        )
    ).allowed


@pytest.mark.unit
@pytest.mark.asyncio
async def test_platform_limit_requests_reserve_raises_when_lua_rejects(
    budget_fake_redis: _BudgetFakeRedis,
) -> None:
    """reserve 在 Lua 脚本判定超限时应抛 ``BudgetExceededError``，而非静默放行。"""
    _ = budget_fake_redis
    service = BudgetService()
    team_id = uuid.uuid4()
    target_id_str = str(team_id)

    await service.reserve(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        limit_requests=1,
        limit_tokens=None,
        estimate_tokens=0,
    )

    with pytest.raises(BudgetExceededError) as exc_info:
        await service.reserve(
            target_kind="tenant",
            target_id=target_id_str,
            period="daily",
            limit_requests=1,
            limit_tokens=None,
            estimate_tokens=0,
        )
    assert exc_info.value.scope == "tenant"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_platform_limit_requests_zero_means_unlimited(
    budget_fake_redis: _BudgetFakeRedis,
) -> None:
    """``limit_requests=0`` 与 ``None`` 等价：不限制、不预扣。"""
    _ = budget_fake_redis
    service = BudgetService()
    team_id = uuid.uuid4()
    target_id_str = str(team_id)

    check = await service.check_budget(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        limit_usd=None,
        limit_tokens=None,
        limit_requests=0,
    )
    assert check.allowed

    reserved_requests, _ = await service.reserve(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        limit_requests=0,
        limit_tokens=None,
        estimate_tokens=0,
    )
    assert reserved_requests == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_platform_limit_requests_read_batch_reflects_reservations(
    budget_fake_redis: _BudgetFakeRedis,
) -> None:
    """``read_budget_usage_batch`` 必须读到 reserve 累加的 requests 计数。"""
    _ = budget_fake_redis
    service = BudgetService()
    team_id = uuid.uuid4()
    target_id_str = str(team_id)

    await service.reserve(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        limit_requests=5,
        limit_tokens=None,
        estimate_tokens=0,
    )

    coord = BudgetUsageCoord(
        target_kind="tenant",
        target_id=target_id_str,
        period="daily",
        model_segment=None,
    )
    batch = await service.read_budget_usage_batch([coord])
    used_cost, used_tokens, used_requests = batch[coord]
    assert used_requests == 1
    assert used_cost == Decimal("0")
    assert used_tokens == 0
