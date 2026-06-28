"""配额规则实时用量快照按团队隔离读取成员护栏桶单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
import uuid

import pytest

from domains.gateway.application.usage.management.budget_usage_reads import (
    BudgetWindowLookup,
    resolve_budget_window_key,
)
from domains.gateway.application.quota.management.quota_plan_usage_reads import QuotaUsageTotals
from domains.gateway.application.quota.management.quota_rule_read_model import (
    QuotaRuleKey,
    QuotaRuleLimits,
    QuotaRuleReadModel,
    QuotaRuleSourceRef,
)
import domains.gateway.application.quota.management.quota_usage_snapshot as mod


def _member_total_rule(team_id: uuid.UUID, user_id: uuid.UUID) -> QuotaRuleReadModel:
    budget_id = uuid.uuid4()
    key = QuotaRuleKey(
        team_id=team_id,
        layer="platform",
        user_id=user_id,
        credential_id=None,
        model_name=None,
        period="monthly",
        window_seconds=None,
        reset_strategy=None,
        access_kind="none",
        access_id=None,
        quota_label=None,
        target_kind="user",
        target_id=user_id,
    )
    return QuotaRuleReadModel(
        key=key,
        source_ref=QuotaRuleSourceRef(layer="platform", budget_id=budget_id),
        limits=QuotaRuleLimits(
            limit_usd=Decimal("200"),
            soft_limit_usd=None,
            limit_tokens=None,
            limit_requests=None,
        ),
        usage=None,
        plan_label=None,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_member_total_usage_reads_db_not_redis(monkeypatch) -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    captured: dict[str, object] = {}

    class _FakePlatformReadService:
        def __init__(self, _session: object) -> None:
            pass

        async def batch_usage_for_budget_windows(self, lookups, *, now=None):
            captured["lookups"] = list(lookups)
            when = now or datetime.now(UTC)
            key = resolve_budget_window_key(lookups[0], now=when)
            return {
                key: QuotaUsageTotals(
                    cost_usd=Decimal("42"),
                    tokens=7,
                    requests=3,
                )
            }

    monkeypatch.setattr(mod, "PlatformBudgetUsageReadService", _FakePlatformReadService)

    rule = _member_total_rule(team_id, user_id)
    [enriched] = await mod.enrich_quota_rules_with_usage([rule], session=MagicMock())

    assert enriched.usage is not None
    assert enriched.usage.current_usd == Decimal("42")
    lookup = captured["lookups"][0]  # type: ignore[index]
    assert isinstance(lookup, BudgetWindowLookup)
    assert lookup.tenant_id == team_id
    assert lookup.target_kind == "user"
    assert lookup.target_id == user_id
