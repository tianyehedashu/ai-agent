"""resolve_model_or_route 进程内缓存。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from domains.gateway.application.catalog.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.grant import resolve_model_cache as rmc
from domains.gateway.application.grant.resolve_model_cache import (
    CACHE_MISS,
    clear_resolve_model_cache_for_tests,
    invalidate_for_tenant,
    peek_resolve_cache_entry,
    put_resolve_cache_entry,
)


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_resolve_model_cache_for_tests()

    # 测试环境无 Redis：版本号恒为空串，与 put 默认 version="" 匹配，避免误失效
    async def _no_redis_version(_team_id: uuid.UUID) -> str:
        return ""

    monkeypatch.setattr(rmc, "_fetch_tenant_version", _no_redis_version)


async def test_negative_cache_round_trip() -> None:
    team_id = uuid.uuid4()
    put_resolve_cache_entry(team_id, "missing-model", user_id=None, resolved=None)
    hit = await peek_resolve_cache_entry(team_id, "missing-model", user_id=None)
    assert hit is not CACHE_MISS
    assert hit is None  # 负缓存返回 None（不再是 dataclass 包装）


def _model_record(team_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=team_id,
        name="my-model",
        capability="chat",
        real_model="gpt-4",
        credential_id=uuid.uuid4(),
        provider="openai",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        enabled=True,
        tags={"prompt_cache": {"enabled": True}},
        upstream_call_shape=None,
        created_by_user_id=None,
        last_test_status=None,
        last_tested_at=None,
        last_test_reason=None,
    )


def _route_record(team_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=team_id,
        virtual_model="smart-route",
        primary_models=["my-model"],
        fallbacks_general=[],
        fallbacks_content_policy=[],
        fallbacks_context_window=[],
        strategy="simple-shuffle",
        retry_policy={"retries": 2},
        enabled=True,
    )


async def test_positive_cache_returns_snapshot() -> None:
    team_id = uuid.uuid4()
    record = _model_record(team_id)
    resolved = ResolvedModelName(record=record, route=None, via_route=None)  # type: ignore[arg-type]
    put_resolve_cache_entry(team_id, "my-model", user_id=None, resolved=resolved)
    hit = await peek_resolve_cache_entry(team_id, "my-model", user_id=None)
    assert hit is not CACHE_MISS
    assert hit is not None
    assert isinstance(hit, ResolvedModelName)
    assert hit is not resolved
    assert hit.record is not record
    assert hit.record.id == record.id
    assert hit.record.provider == "openai"
    assert hit.record.real_model == "gpt-4"

    record.tags["prompt_cache"]["enabled"] = False
    assert hit.record.tags == {"prompt_cache": {"enabled": True}}


async def test_positive_route_cache_returns_snapshot() -> None:
    team_id = uuid.uuid4()
    record = _model_record(team_id)
    route = _route_record(team_id)
    resolved = ResolvedModelName(
        record=record,
        route=route,
        via_route=route.virtual_model,
    )  # type: ignore[arg-type]

    put_resolve_cache_entry(team_id, "smart-route", user_id=None, resolved=resolved)
    hit = await peek_resolve_cache_entry(team_id, "smart-route", user_id=None)

    assert isinstance(hit, ResolvedModelName)
    assert hit.route is not None
    assert hit.route is not route
    assert hit.route.virtual_model == "smart-route"
    assert hit.route.primary_models == ["my-model"]
    assert hit.via_route == "smart-route"


def test_invalidate_for_tenant() -> None:
    team_id = uuid.uuid4()
    other_team = uuid.uuid4()
    put_resolve_cache_entry(team_id, "a", user_id=None, resolved=None)
    put_resolve_cache_entry(other_team, "b", user_id=None, resolved=None)
    invalidate_for_tenant(team_id)
    # 同步签名：本地 L1 立即清空；peek 为 async，但 L1 已无对应条目，
    # 必然返回 CACHE_MISS（不依赖 Redis 版本号）
    import asyncio

    async def _check() -> None:
        assert await peek_resolve_cache_entry(team_id, "a", user_id=None) is CACHE_MISS
        assert await peek_resolve_cache_entry(other_team, "b", user_id=None) is not CACHE_MISS

    asyncio.run(_check())
