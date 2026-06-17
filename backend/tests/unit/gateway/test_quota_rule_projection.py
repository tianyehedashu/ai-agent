"""Quota rule projection 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from domains.gateway.application.management.plan_read_models import (
    PlanQuotaReadModel,
    ProviderPlanReadModel,
)
from domains.gateway.application.management.quota_rule_read_mappers import (
    budget_to_quota_rule,
    flatten_provider_plan,
)
from domains.gateway.infrastructure.models.budget import GatewayBudget


def test_budget_to_quota_rule_user() -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    budget = GatewayBudget(
        target_kind="user",
        target_id=user_id,
        period="monthly",
        model_name="gpt-4",
        limit_usd=Decimal("50"),
    )
    budget.id = uuid.uuid4()
    rule = budget_to_quota_rule(budget, team_id=team_id)
    assert rule.key.layer == "platform"
    assert rule.key.user_id == user_id
    assert rule.key.model_name == "gpt-4"
    assert rule.limits.limit_usd == Decimal("50")
    assert rule.usage is not None
    assert rule.usage.window_start is not None
    assert rule.usage.reset_at is not None


def test_budget_to_quota_rule_total_has_window_start_only() -> None:
    team_id = uuid.uuid4()
    budget = GatewayBudget(
        target_kind="tenant",
        target_id=team_id,
        period="total",
        limit_usd=Decimal("100"),
    )
    budget.id = uuid.uuid4()
    rule = budget_to_quota_rule(budget, team_id=team_id)
    assert rule.usage is not None
    assert rule.usage.window_start == datetime(1970, 1, 1, tzinfo=UTC)
    assert rule.usage.reset_at is None


def test_flatten_provider_plan_expands_quotas() -> None:
    team_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    plan = ProviderPlanReadModel(
        id=plan_id,
        credential_id=cred_id,
        real_model="claude-3",
        label="Pro",
        valid_from=__import__("datetime").datetime.now(__import__("datetime").UTC),
        valid_until=__import__("datetime").datetime.now(__import__("datetime").UTC),
        is_active=True,
        auto_renew=False,
        notes=None,
        extra=None,
        quotas=(
            PlanQuotaReadModel(
                id=uuid.uuid4(),
                label="5h",
                window_seconds=18000,
                reset_strategy="rolling",
                limit_usd=Decimal("10"),
                limit_tokens=None,
                limit_requests=None,
            ),
            PlanQuotaReadModel(
                id=uuid.uuid4(),
                label="total",
                window_seconds=0,
                reset_strategy="rolling",
                limit_usd=Decimal("100"),
                limit_tokens=None,
                limit_requests=None,
            ),
        ),
    )
    rules = flatten_provider_plan(plan, team_id=team_id)
    assert len(rules) == 2
    assert {r.key.quota_label for r in rules} == {"5h", "total"}
    assert all(r.key.layer == "upstream" for r in rules)
    assert all(r.key.credential_id == cred_id for r in rules)
    rolling = next(r for r in rules if r.key.quota_label == "5h")
    assert rolling.usage is not None
    assert rolling.usage.window_start is not None
    assert rolling.usage.reset_at is not None
