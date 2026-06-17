"""配额用量手工校正单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

import pytest

from domains.gateway.application.management.quota_usage_adjustment import (
    QuotaUsageAdjustmentCommand,
    _resolved_usage_values,
)
from libs.exceptions import ValidationError


def test_resolved_usage_values_reset_window() -> None:
    usd, tokens, requests = _resolved_usage_values(
        QuotaUsageAdjustmentCommand(layer="platform", budget_id=uuid.uuid4(), mode="reset_window")
    )
    assert usd == Decimal("0")
    assert tokens == 0
    assert requests == 0


def test_resolved_usage_values_set_requires_field() -> None:
    with pytest.raises(ValidationError):
        _resolved_usage_values(
            QuotaUsageAdjustmentCommand(layer="platform", budget_id=uuid.uuid4(), mode="set")
        )


@pytest.mark.asyncio
async def test_apply_platform_usage_adjustment(db_session, test_user) -> None:
    from domains.gateway.application.management.quota_usage_adjustment import (
        apply_quota_usage_adjustment,
    )
    from domains.gateway.infrastructure.models.budget import GatewayBudget
    from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
    from domains.tenancy.application import TeamService

    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    budget = GatewayBudget(
        target_kind="tenant",
        target_id=team.id,
        period="daily",
        limit_usd=Decimal("100"),
    )
    db_session.add(budget)
    await db_session.flush()

    await apply_quota_usage_adjustment(
        db_session,
        QuotaUsageAdjustmentCommand(
            layer="platform",
            budget_id=budget.id,
            mode="set",
            current_usd=Decimal("12.50"),
            current_tokens=1000,
            current_requests=5,
        ),
    )
    await db_session.commit()

    row = await BudgetRepository(db_session).get(budget.id)
    assert row is not None
    assert row.current_usd == Decimal("12.50")
    assert row.current_tokens == 1000
    assert row.current_requests == 5

    from domains.gateway.application.management.budget_usage_reads import (
        BudgetWindowLookup,
        resolve_budget_window_key,
    )
    from domains.gateway.domain.quota_plan import PLATFORM_NS

    lookup = BudgetWindowLookup(
        budget_id=budget.id,
        period=budget.period,
        target_kind=budget.target_kind,
        target_id=budget.target_id,
        model_name=budget.model_name,
        credential_id=budget.credential_id,
        tenant_id=budget.tenant_id,
    )
    key = resolve_budget_window_key(lookup, now=datetime.now(UTC))
    from sqlalchemy import select

    from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (
        GatewayQuotaPlanUsageBucket,
    )

    result = await db_session.execute(
        select(GatewayQuotaPlanUsageBucket).where(
            GatewayQuotaPlanUsageBucket.ns == PLATFORM_NS,
            GatewayQuotaPlanUsageBucket.plan_id == budget.id,
            GatewayQuotaPlanUsageBucket.quota_id == budget.id,
            GatewayQuotaPlanUsageBucket.window_start == key.window_start,
        )
    )
    bucket = result.scalar_one()
    assert bucket.cost_usd == Decimal("12.50")
    assert bucket.tokens == 1000
    assert bucket.requests == 5


@pytest.mark.asyncio
async def test_apply_upstream_rolling_adjustment_rejected(db_session) -> None:
    """滚动窗口配额展示读走日志、忽略桶，手工校正应被拒绝并给出引导。"""
    from datetime import timedelta

    from domains.gateway.application.management.quota_usage_adjustment import (
        apply_quota_usage_adjustment,
    )
    from domains.gateway.infrastructure.repositories.provider_plan_repository import (
        ProviderPlanRepository,
    )

    now = datetime.now(UTC)
    repo = ProviderPlanRepository(db_session)
    plan = await repo.create(
        credential_id=uuid.uuid4(),
        real_model=None,
        label="rolling-pack",
        valid_from=now,
        valid_until=now + timedelta(days=30),
    )
    quota = await repo.add_quota(
        plan_id=plan.id,
        label="5h",
        window_seconds=18000,
        reset_strategy="rolling",
        limit_tokens=1_000_000,
    )

    with pytest.raises(ValidationError, match="滚动窗口"):
        await apply_quota_usage_adjustment(
            db_session,
            QuotaUsageAdjustmentCommand(
                layer="upstream",
                plan_id=plan.id,
                quota_id=quota.id,
                mode="set",
                current_tokens=100,
            ),
        )
