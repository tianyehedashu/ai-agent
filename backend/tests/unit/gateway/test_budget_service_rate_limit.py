"""BudgetService.check_rate_limit 单测（Lua 原子化限流）。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from domains.gateway.application.budget.budget_service import (
    _RATE_LIMIT_RPM_LUA_SCRIPT,
    _RATE_LIMIT_TPM_LUA_SCRIPT,
    BudgetService,
)
from domains.gateway.domain.errors import RateLimitExceededError


@pytest.mark.asyncio
async def test_check_rate_limit_calls_rpm_lua_script(monkeypatch) -> None:
    """rpm 限制生效时应调用 RPM Lua 脚本并解析结果。"""
    service = BudgetService()
    fake_client = AsyncMock()
    fake_client.eval.return_value = [1, 0]
    monkeypatch.setattr(
        "domains.gateway.application.budget.budget_service.get_redis_client",
        AsyncMock(return_value=fake_client),
    )

    await service.check_rate_limit(
        target_kind="team",
        target_id="team-1",
        rpm_limit=10,
        tpm_limit=None,
        estimate_tokens=0,
    )

    assert fake_client.eval.await_count == 1
    call_args = fake_client.eval.await_args.args
    assert call_args[0] == _RATE_LIMIT_RPM_LUA_SCRIPT
    assert call_args[1] == 1
    assert call_args[2] == "gateway:rate:team:team-1:rpm"


@pytest.mark.asyncio
async def test_check_rate_limit_calls_tpm_lua_script(monkeypatch) -> None:
    """tpm 限制生效时应调用 TPM Lua 脚本并解析结果。"""
    service = BudgetService()
    fake_client = AsyncMock()
    fake_client.eval.return_value = [1, 0]
    monkeypatch.setattr(
        "domains.gateway.application.budget.budget_service.get_redis_client",
        AsyncMock(return_value=fake_client),
    )

    await service.check_rate_limit(
        target_kind="team",
        target_id="team-1",
        rpm_limit=None,
        tpm_limit=1000,
        estimate_tokens=100,
    )

    assert fake_client.eval.await_count == 1
    call_args = fake_client.eval.await_args.args
    assert call_args[0] == _RATE_LIMIT_TPM_LUA_SCRIPT
    assert call_args[1] == 1
    assert call_args[2] == "gateway:rate:team:team-1:tpm"


@pytest.mark.asyncio
async def test_check_rate_limit_rpm_exceeded_raises(monkeypatch) -> None:
    """Lua 脚本返回 rpm 超限时抛出 RateLimitExceededError。"""
    service = BudgetService()
    fake_client = AsyncMock()
    fake_client.eval.return_value = [-1, 10]
    monkeypatch.setattr(
        "domains.gateway.application.budget.budget_service.get_redis_client",
        AsyncMock(return_value=fake_client),
    )

    with pytest.raises(RateLimitExceededError) as exc_info:
        await service.check_rate_limit(
            target_kind="team",
            target_id="team-1",
            rpm_limit=10,
            tpm_limit=None,
            estimate_tokens=0,
        )
    assert exc_info.value.scope == "team:rpm"


@pytest.mark.asyncio
async def test_check_rate_limit_tpm_exceeded_raises(monkeypatch) -> None:
    """Lua 脚本返回 tpm 超限时抛出 RateLimitExceededError。"""
    service = BudgetService()
    fake_client = AsyncMock()
    fake_client.eval.return_value = [0, 900]
    monkeypatch.setattr(
        "domains.gateway.application.budget.budget_service.get_redis_client",
        AsyncMock(return_value=fake_client),
    )

    with pytest.raises(RateLimitExceededError) as exc_info:
        await service.check_rate_limit(
            target_kind="team",
            target_id="team-1",
            rpm_limit=None,
            tpm_limit=1000,
            estimate_tokens=200,
        )
    assert exc_info.value.scope == "team:tpm"


@pytest.mark.asyncio
async def test_check_rate_limit_no_limits_short_circuits(monkeypatch) -> None:
    """无 rpm/tpm 限制时不调用 Redis。"""
    service = BudgetService()
    fake_client = AsyncMock()
    monkeypatch.setattr(
        "domains.gateway.application.budget.budget_service.get_redis_client",
        AsyncMock(return_value=fake_client),
    )

    await service.check_rate_limit(
        target_kind="team",
        target_id="team-1",
        rpm_limit=None,
        tpm_limit=None,
        estimate_tokens=100,
    )

    fake_client.eval.assert_not_awaited()
