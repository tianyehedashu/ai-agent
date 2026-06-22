"""EntitlementPlan callback 结算单测。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application import entitlement_plan_callback_settlement as mod
from domains.gateway.domain.quota_plan import ENTITLEMENT_NS, PlanQuotaSpec


@pytest.mark.asyncio
async def test_commit_entitlement_plan_on_success(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(quota_id=quota_id, label="monthly", window_seconds=0, limit_tokens=1_000_000)

    quota = MagicMock()
    quota.commit = AsyncMock()
    quota.release = AsyncMock()
    schedule = AsyncMock()
    monkeypatch.setattr(mod, "get_quota_plan_service", lambda: quota)
    monkeypatch.setattr(mod, "_load_plan_specs", AsyncMock(return_value={quota_id: spec}))
    monkeypatch.setattr(mod, "schedule_quota_plan_usage_upsert", schedule)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    redis_mock = AsyncMock(return_value=mock_client)
    monkeypatch.setattr(mod, "get_redis_client", redis_mock)
    monkeypatch.setattr(
        "domains.gateway.application.quota_plan_callback_settlement_shared.get_redis_client",
        redis_mock,
    )

    metadata: dict[str, Any] = {
        "gateway_entitlement_plan_id": str(plan_id),
        "gateway_entitlement_plan_reservations": [
            {"quota_id": str(quota_id), "minute_unix": 1, "reserved_requests": 1}
        ],
    }

    await mod.settle_entitlement_plan_from_callback(
        metadata=metadata,
        status="success",
        cost_usd=Decimal("0"),
        total_tokens=500,
        request_id="req-e1",
    )

    quota.commit.assert_awaited_once()
    quota.release.assert_not_awaited()
    schedule.assert_called_once()
    kwargs = schedule.call_args.kwargs
    assert kwargs["ns"] == ENTITLEMENT_NS
    assert kwargs["plan_id"] == plan_id
    assert kwargs["request_id"] == "req-e1"
    assert kwargs["settled_at"] is not None


@pytest.mark.asyncio
async def test_skips_commit_when_proxy_already_settled(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(quota_id=quota_id, label="monthly", window_seconds=0)

    quota = MagicMock()
    quota.commit = AsyncMock()
    schedule = AsyncMock()
    monkeypatch.setattr(mod, "get_quota_plan_service", lambda: quota)
    monkeypatch.setattr(mod, "_load_plan_specs", AsyncMock(return_value={quota_id: spec}))
    monkeypatch.setattr(mod, "schedule_quota_plan_usage_upsert", schedule)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=b"1")
    monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=mock_client))

    await mod.settle_entitlement_plan_from_callback(
        metadata={
            "gateway_entitlement_plan_id": str(plan_id),
            "gateway_entitlement_plan_reservations": [
                {"quota_id": str(quota_id), "minute_unix": 1, "reserved_requests": 1}
            ],
        },
        status="success",
        cost_usd=Decimal("1"),
        total_tokens=100,
        request_id="req-e2",
    )

    quota.commit.assert_not_awaited()
    schedule.assert_not_called()
