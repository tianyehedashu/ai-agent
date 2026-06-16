"""Platform 预算展示读与日志维度单测。"""

from __future__ import annotations

from decimal import Decimal
import uuid

from domains.gateway.application.management.budget_usage_reads import merge_platform_display_totals
from domains.gateway.application.management.quota_plan_usage_reads import QuotaUsageTotals
from domains.gateway.domain.platform_budget_display import (
    PlatformBudgetLogScope,
    platform_log_fallback_supported,
)


def test_merge_display_totals_takes_per_dimension_max() -> None:
    bucket = QuotaUsageTotals(cost_usd=Decimal("0.01"), tokens=100, requests=1)
    logs = QuotaUsageTotals(cost_usd=Decimal("0.50"), tokens=10_000, requests=5)
    merged = merge_platform_display_totals(bucket, logs)
    assert merged.cost_usd == Decimal("0.50")
    assert merged.tokens == 10_000
    assert merged.requests == 5


def test_merge_display_totals_prefers_bucket_when_higher() -> None:
    bucket = QuotaUsageTotals(cost_usd=Decimal("1.00"), tokens=5000, requests=3)
    logs = QuotaUsageTotals(cost_usd=Decimal("0.20"), tokens=3000, requests=2)
    merged = merge_platform_display_totals(bucket, logs)
    assert merged.cost_usd == Decimal("1.00")
    assert merged.tokens == 5000
    assert merged.requests == 3


def test_system_target_skips_log_fallback() -> None:
    scope = PlatformBudgetLogScope(
        target_kind="system",
        target_id=None,
        model_name=None,
        credential_id=None,
        tenant_id=None,
    )
    assert platform_log_fallback_supported(scope) is False


def test_tenant_target_supports_log_fallback() -> None:
    scope = PlatformBudgetLogScope(
        target_kind="tenant",
        target_id=uuid.uuid4(),
        model_name="gpt-alias",
        credential_id=None,
        tenant_id=None,
    )
    assert platform_log_fallback_supported(scope) is True
