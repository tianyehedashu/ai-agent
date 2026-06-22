"""proxy settle_usage 下游 entitlement 汇总表单测。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
import uuid

import pytest

from domains.gateway.application import proxy_response_adapter as mod
from domains.gateway.application.proxy_context import EntitlementReservationState, ProxyContext
from domains.gateway.domain.quota_plan import ENTITLEMENT_NS, PlanQuotaSpec
from domains.gateway.domain.types import GatewayCapability


class _CommitRecordingEntitlementGuard:
    def __init__(self) -> None:
        self.committed = False

    async def commit(
        self,
        plan_id: uuid.UUID,
        specs: list[PlanQuotaSpec],
        *,
        delta_tokens: int,
        delta_usd: Decimal,
    ) -> None:
        _ = plan_id, specs, delta_tokens, delta_usd
        self.committed = True


class _NoopBudget:
    async def commit(self, *args: object, **kwargs: object) -> None:
        _ = args, kwargs


@pytest.mark.asyncio
async def test_settle_usage_schedules_entitlement_bucket_upsert(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(quota_id=quota_id, label="monthly", window_seconds=86400, limit_tokens=1000)
    request_id = "req-proxy-ent"
    ctx = ProxyContext(
        team_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id=request_id,
        store_full_messages=False,
        guardrail_enabled=False,
        budget_model="gpt-4o-mini",
        entitlement_state=EntitlementReservationState(
            plan_id=plan_id,
            plan_label="pkg",
            specs=[spec],
            reservations=[],
        ),
    )
    guard = _CommitRecordingEntitlementGuard()
    schedule = AsyncMock()
    monkeypatch.setattr(mod, "schedule_quota_plan_usage_upsert", schedule)
    monkeypatch.setattr(mod, "get_session_context", lambda: _DummySessionCM())
    monkeypatch.setattr(mod, "BudgetRepository", _FakeEmptyRepo)
    record_proxy = AsyncMock()
    monkeypatch.setattr(
        "domains.gateway.application.entitlement_plan_callback_settlement.record_proxy_entitlement_commit",
        record_proxy,
    )

    await mod.settle_usage(
        ctx,
        _NoopBudget(),
        tokens=120,
        cost=Decimal("0.05"),
        requests=1,
        entitlement_guard=guard,  # type: ignore[arg-type]
        request_id=request_id,
    )

    assert guard.committed
    record_proxy.assert_awaited_once_with(request_id)
    schedule.assert_called_once()
    kwargs = schedule.call_args.kwargs
    assert kwargs["ns"] == ENTITLEMENT_NS
    assert kwargs["plan_id"] == plan_id
    assert kwargs["delta_tokens"] == 120
    assert kwargs["request_id"] == request_id


class _DummySessionCM:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeEmptyRepo:
    def __init__(self, _session: object) -> None:
        pass

    async def get_many_by_plan(self, _plan: object) -> dict[object, object]:
        return {}

    async def get_for(self, *args: object, **kwargs: object) -> None:
        _ = args, kwargs
        return None
