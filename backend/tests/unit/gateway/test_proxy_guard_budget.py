"""ProxyGuard.check_budget 单测（hard limit 阻断 + 预扣）。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.budget_config_cache import BudgetConfigRow
from domains.gateway.application.budget_service import (
    BudgetCheckResult,
    BudgetService,
    BudgetUsageCoord,
)
from domains.gateway.application.proxy_context import ProxyContext
from domains.gateway.application.proxy_guard import ProxyGuard
from domains.gateway.domain.errors import BudgetExceededError
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal


def _ctx(*, team_id: uuid.UUID) -> ProxyContext:
    vkey_id = uuid.uuid4()
    return ProxyContext(
        team_id=team_id,
        user_id=None,
        vkey=VirtualKeyPrincipal(
            vkey_id=vkey_id,
            vkey_name="test",
            team_id=team_id,
            user_id=None,
            allowed_models=(),
            allowed_capabilities=(),
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=False,
            guardrail_enabled=False,
            is_system=False,
        ),
        capability=GatewayCapability.CHAT,
        request_id="req-1",
        store_full_messages=False,
        guardrail_enabled=False,
        budget_model=None,
    )


def _tenant_monthly_row(
    team_id: uuid.UUID,
) -> tuple[tuple[str, uuid.UUID | None, str, str | None, uuid.UUID | None], BudgetConfigRow]:
    row = BudgetConfigRow(
        target_kind="tenant",
        target_id=team_id,
        period="monthly",
        model_name=None,
        limit_usd=Decimal("10"),
        limit_tokens=None,
        limit_requests=None,
    )
    return (
        row.target_kind,
        row.target_id,
        row.period,
        row.model_name,
        row.credential_id,
        row.tenant_id,
    ), row


@pytest.mark.asyncio
async def test_check_budget_raises_when_tenant_usd_exceeded(monkeypatch) -> None:
    team_id = uuid.uuid4()
    ctx = _ctx(team_id=team_id)
    coord, config_row = _tenant_monthly_row(team_id)

    async def fake_cached(_plan, _loader):
        return {coord: config_row}

    monkeypatch.setattr(
        "domains.gateway.application.proxy_guard.get_cached_budget_by_plan",
        fake_cached,
    )

    usage_coord = BudgetUsageCoord(
        target_kind="tenant",
        target_id=str(team_id),
        period="monthly",
        model_segment=None,
    )
    budget_service = BudgetService()
    budget_service.read_budget_usage_batch = AsyncMock(
        return_value={usage_coord: (Decimal("10"), 0, 0)}
    )
    budget_service.check_budget = AsyncMock(
        return_value=BudgetCheckResult(
            allowed=False,
            reason="usd",
            used_usd=Decimal("10"),
        )
    )
    budget_service.reserve = AsyncMock()

    guard = ProxyGuard(MagicMock(), budget_service, MagicMock())

    with pytest.raises(BudgetExceededError):
        await guard.check_budget(ctx)


@pytest.mark.asyncio
async def test_check_budget_reserves_requests_when_under_limit(monkeypatch) -> None:
    team_id = uuid.uuid4()
    ctx = _ctx(team_id=team_id)
    row = BudgetConfigRow(
        target_kind="tenant",
        target_id=team_id,
        period="daily",
        model_name=None,
        limit_usd=None,
        limit_tokens=None,
        limit_requests=100,
    )
    coord = (
        row.target_kind,
        row.target_id,
        row.period,
        row.model_name,
        row.credential_id,
        row.tenant_id,
    )

    async def fake_cached(_plan, _loader):
        return {coord: row}

    monkeypatch.setattr(
        "domains.gateway.application.proxy_guard.get_cached_budget_by_plan",
        fake_cached,
    )

    usage_coord = BudgetUsageCoord(
        target_kind="tenant",
        target_id=str(team_id),
        period="daily",
        model_segment=None,
    )
    budget_service = BudgetService()
    budget_service.read_budget_usage_batch = AsyncMock(
        return_value={usage_coord: (Decimal("0"), 0, 0)}
    )
    budget_service.check_budget = AsyncMock(return_value=BudgetCheckResult(allowed=True))
    budget_service.reserve = AsyncMock(return_value=(1, 0))

    guard = ProxyGuard(MagicMock(), budget_service, MagicMock())
    reservations = await guard.check_budget(ctx)

    assert len(reservations) == 1
    assert reservations[0].reserved_requests == 1
    budget_service.reserve.assert_awaited_once()
