"""ORM → 套餐读模型映射：遗留 reset_strategy 归一化。"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest

from domains.gateway.application.quota.management.plan_read_mappers import entitlement_plan_from_orm
from domains.gateway.presentation.plan_response import entitlement_plan_to_response


def _legacy_entitlement_quota_row(*, reset_strategy: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        label="default",
        window_seconds=86400,
        reset_strategy=reset_strategy,
        reset_timezone="UTC",
        reset_time_minutes=0,
        reset_day_of_month=1,
        limit_usd=None,
        limit_tokens=1000,
        limit_requests=None,
        unit_price_usd_per_token=None,
        unit_price_usd_per_request=None,
        enabled=True,
        valid_from=None,
        valid_until=None,
    )


def _legacy_entitlement_plan_row() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        target_kind="vkey",
        target_id=uuid.uuid4(),
        label="Pro",
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        included_models=[],
        included_capabilities=[],
        notes=None,
        extra=None,
    )


@pytest.mark.unit
def test_entitlement_plan_response_normalizes_legacy_plan_anniversary() -> None:
    plan = _legacy_entitlement_plan_row()
    quota = _legacy_entitlement_quota_row(reset_strategy="plan_anniversary")
    read_model = entitlement_plan_from_orm(plan, [quota])
    response = entitlement_plan_to_response(read_model)

    assert len(response.quotas) == 1
    assert response.quotas[0].reset_strategy == "rolling"
