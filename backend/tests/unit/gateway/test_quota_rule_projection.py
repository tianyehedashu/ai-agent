"""Quota rule projection 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from domains.gateway.application.management.plan_read_models import ProviderQuotaReadModel
from domains.gateway.application.management.quota_rule_read_mappers import (
    budget_to_quota_rule,
    provider_quota_to_quota_rule,
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


def test_provider_quota_to_quota_rule_maps_flat_row() -> None:
    team_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    quota = ProviderQuotaReadModel(
        id=rule_id,
        credential_id=cred_id,
        real_model="claude-3",
        label="5h",
        window_seconds=18000,
        reset_strategy="rolling",
        limit_usd=Decimal("10"),
        limit_tokens=None,
        limit_requests=None,
    )
    rule = provider_quota_to_quota_rule(quota, team_id=team_id)
    assert rule.key.layer == "upstream"
    assert rule.key.credential_id == cred_id
    assert rule.key.quota_label == "5h"
    assert rule.source_ref.quota_id == rule_id
    assert rule.source_ref.plan_id is None
    assert rule.plan_label is None
    assert rule.usage is not None
    assert rule.usage.window_start is not None
    assert rule.usage.reset_at is None
