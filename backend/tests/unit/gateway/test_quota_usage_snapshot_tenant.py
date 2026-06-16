"""配额规则实时用量快照按团队隔离读取成员护栏桶单测。"""

from __future__ import annotations

from decimal import Decimal
import uuid

from unittest.mock import MagicMock

import pytest

from domains.gateway.application.budget_service import redis_tenant_segment_for_budget
from domains.gateway.application.management.quota_rule_read_model import (
    QuotaRuleKey,
    QuotaRuleLimits,
    QuotaRuleReadModel,
    QuotaRuleSourceRef,
)
import domains.gateway.application.management.quota_usage_snapshot as mod


def _member_total_rule(team_id: uuid.UUID, user_id: uuid.UUID) -> QuotaRuleReadModel:
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
        source_ref=QuotaRuleSourceRef(layer="platform", budget_id=uuid.uuid4()),
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
async def test_member_total_usage_reads_tenant_segmented_bucket(monkeypatch) -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    captured: dict[str, object] = {}

    class _FakeBudgetService:
        async def read_budget_usage_batch(self, coords):
            captured["coords"] = list(coords)
            return {c: (Decimal("42"), 7, 3) for c in coords}

    monkeypatch.setattr(mod, "BudgetService", _FakeBudgetService)

    rule = _member_total_rule(team_id, user_id)
    [enriched] = await mod.enrich_quota_rules_with_usage([rule], session=MagicMock())

    assert enriched.usage is not None
    assert enriched.usage.current_usd == Decimal("42")
    # 用量桶坐标须带按团队隔离的 tenant 段。
    coord = captured["coords"][0]  # type: ignore[index]
    assert coord.tenant_segment == redis_tenant_segment_for_budget(team_id)
    assert coord.tenant_segment is not None
