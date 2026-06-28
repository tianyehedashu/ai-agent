"""配额用量 enrich 上游扁平规则单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
import uuid

import pytest

from domains.gateway.application.quota.management.quota_plan_usage_reads import QuotaUsageTotals
from domains.gateway.application.quota.management.quota_rule_read_model import (
    QuotaRuleKey,
    QuotaRuleLimits,
    QuotaRuleReadModel,
    QuotaRuleSourceRef,
)
import domains.gateway.application.quota.management.quota_usage_snapshot as mod


def _upstream_rule(rule_id: uuid.UUID) -> QuotaRuleReadModel:
    return QuotaRuleReadModel(
        key=QuotaRuleKey(
            team_id=uuid.uuid4(),
            layer="upstream",
            user_id=None,
            credential_id=uuid.uuid4(),
            model_name="gpt-4o",
            period=None,
            window_seconds=86400,
            reset_strategy="calendar_daily_utc",
            access_kind="none",
            access_id=None,
            quota_label="daily",
            target_kind=None,
            target_id=None,
        ),
        source_ref=QuotaRuleSourceRef(layer="upstream", quota_id=rule_id),
        limits=QuotaRuleLimits(
            limit_usd=Decimal("10"),
            soft_limit_usd=None,
            limit_tokens=None,
            limit_requests=None,
        ),
        usage=None,
        plan_label=None,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_enrich_upstream_flat_rule_with_quota_id_only(monkeypatch) -> None:
    """上游 source_ref 仅 quota_id 时也应填充实时用量。"""
    rule_id = uuid.uuid4()
    captured: dict[str, object] = {}

    class _FakeQuotaReadService:
        def __init__(self, _session: object) -> None:
            pass

        async def batch_usage_for_quota_windows(self, lookups, *, now=None):
            captured["lookups"] = list(lookups)
            when = now or datetime.now(UTC)
            from domains.gateway.application.quota.management.quota_plan_usage_reads import (
                resolve_quota_window_key,
            )

            key = resolve_quota_window_key(lookups[0], now=when)
            return {key: QuotaUsageTotals(cost_usd=Decimal("3"), tokens=100, requests=2)}

    monkeypatch.setattr(mod, "QuotaPlanUsageReadService", _FakeQuotaReadService)

    [enriched] = await mod.enrich_quota_rules_with_usage(
        [_upstream_rule(rule_id)], session=MagicMock()
    )

    assert enriched.usage is not None
    assert enriched.usage.current_usd == Decimal("3")
    lookups = captured["lookups"]
    assert len(lookups) == 1
    assert lookups[0].plan_id == rule_id
    assert lookups[0].quota_id == rule_id


@pytest.mark.asyncio
async def test_enrich_downstream_requires_plan_and_quota_id(monkeypatch) -> None:
    """下游仍要求 plan_id + quota_id 双键。"""
    captured: dict[str, object] = {"called": False}

    class _FakeQuotaReadService:
        def __init__(self, _session: object) -> None:
            pass

        async def batch_usage_for_quota_windows(self, lookups, *, now=None):
            captured["called"] = True
            return {}

    monkeypatch.setattr(mod, "QuotaPlanUsageReadService", _FakeQuotaReadService)

    downstream_only_quota = QuotaRuleReadModel(
        key=QuotaRuleKey(
            team_id=uuid.uuid4(),
            layer="downstream",
            user_id=None,
            credential_id=None,
            model_name=None,
            period=None,
            window_seconds=86400,
            reset_strategy="rolling",
            access_kind="vkey",
            access_id=uuid.uuid4(),
            quota_label="daily",
            target_kind="vkey",
            target_id=uuid.uuid4(),
        ),
        source_ref=QuotaRuleSourceRef(layer="downstream", quota_id=uuid.uuid4()),
        limits=QuotaRuleLimits(
            limit_usd=None,
            soft_limit_usd=None,
            limit_tokens=None,
            limit_requests=None,
        ),
        usage=None,
        plan_label="pack",
        is_active=True,
    )

    [enriched] = await mod.enrich_quota_rules_with_usage(
        [downstream_only_quota], session=MagicMock()
    )

    assert captured["called"] is False
    assert enriched.usage is None
