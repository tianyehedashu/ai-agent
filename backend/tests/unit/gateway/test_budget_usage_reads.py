"""Platform 预算展示读：桶/日志合并与日志归因单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.budget_usage_reads import (
    BudgetWindowLookup,
    PlatformBudgetUsageReadService,
    _log_dimension_clauses,
    merge_platform_display_totals,
    resolve_budget_window_key,
)
from domains.gateway.application.management.quota_plan_usage_reads import QuotaUsageTotals
from domains.gateway.domain.platform_budget_display import (
    PlatformBudgetLogScope,
    platform_log_fallback_supported,
)
from domains.gateway.domain.quota_plan import PLATFORM_NS

_WHEN = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)


def _lookup(*, target_kind: str = "tenant", tenant_id: uuid.UUID | None = None) -> BudgetWindowLookup:
    return BudgetWindowLookup(
        budget_id=uuid.uuid4(),
        period="monthly",
        target_kind=target_kind,
        target_id=uuid.uuid4(),
        model_name=None,
        credential_id=None,
        tenant_id=tenant_id,
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


def test_user_log_scope_with_tenant_uses_member_visibility_sql() -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    scope = PlatformBudgetLogScope(
        target_kind="user",
        target_id=user_id,
        model_name=None,
        credential_id=None,
        tenant_id=team_id,
    )
    compiled = " ".join(str(clause.compile(compile_kwargs={"literal_binds": True})) for clause in _log_dimension_clauses(scope))
    assert "gateway_request_logs.tenant_id" in compiled
    assert "gateway_virtual_keys" in compiled
    assert "vkey_id IS NULL" in compiled


@pytest.mark.asyncio
async def test_non_zero_bucket_merges_with_logs(monkeypatch) -> None:
    """非零桶与日志窗口取 max，避免 settlement 截断。"""
    lookup = _lookup()
    key = resolve_budget_window_key(lookup, now=_WHEN)
    row = SimpleNamespace(cost_usd=Decimal("3"), tokens=30, requests=3)
    log_total = QuotaUsageTotals(cost_usd=Decimal("5"), tokens=50, requests=5)

    service = PlatformBudgetUsageReadService(MagicMock())
    aggregate = AsyncMock(return_value={key: log_total})
    monkeypatch.setattr(
        service,
        "_load_buckets",
        AsyncMock(
            return_value={
                (PLATFORM_NS, lookup.budget_id, lookup.budget_id, key.window_start): row
            }
        ),
    )
    monkeypatch.setattr(service, "_aggregate_logs", aggregate)

    out = await service.batch_usage_for_budget_windows([lookup], now=_WHEN)

    assert out[key] == log_total
    aggregate.assert_awaited_once()


@pytest.mark.asyncio
async def test_bucket_cleared_to_zero_is_respected(monkeypatch) -> None:
    """reset_window 清零后桶值为 0，展示读必须显示 0，不被日志拉回。"""
    lookup = _lookup()
    key = resolve_budget_window_key(lookup, now=_WHEN)
    row = SimpleNamespace(cost_usd=Decimal("0"), tokens=0, requests=0)

    service = PlatformBudgetUsageReadService(MagicMock())
    aggregate = AsyncMock()
    monkeypatch.setattr(
        service,
        "_load_buckets",
        AsyncMock(
            return_value={
                (PLATFORM_NS, lookup.budget_id, lookup.budget_id, key.window_start): row
            }
        ),
    )
    monkeypatch.setattr(service, "_aggregate_logs", aggregate)

    out = await service.batch_usage_for_budget_windows([lookup], now=_WHEN)

    assert out[key] == QuotaUsageTotals(cost_usd=Decimal("0"), tokens=0, requests=0)
    aggregate.assert_not_awaited()


@pytest.mark.asyncio
async def test_bucket_missing_falls_back_to_logs(monkeypatch) -> None:
    """桶缺失且维度可日志归因时，用请求日志兜底。"""
    lookup = _lookup()
    key = resolve_budget_window_key(lookup, now=_WHEN)
    log_total = QuotaUsageTotals(cost_usd=Decimal("5"), tokens=50, requests=5)

    service = PlatformBudgetUsageReadService(MagicMock())
    monkeypatch.setattr(service, "_load_buckets", AsyncMock(return_value={}))
    monkeypatch.setattr(service, "_aggregate_logs", AsyncMock(return_value={key: log_total}))

    out = await service.batch_usage_for_budget_windows([lookup], now=_WHEN)

    assert out[key] == log_total


@pytest.mark.asyncio
async def test_system_dimension_missing_bucket_is_zero(monkeypatch) -> None:
    """system 维度无稳定日志归因：桶缺失时记 0，不走日志兜底。"""
    lookup = _lookup(target_kind="system")
    key = resolve_budget_window_key(lookup, now=_WHEN)

    service = PlatformBudgetUsageReadService(MagicMock())
    aggregate = AsyncMock()
    monkeypatch.setattr(service, "_load_buckets", AsyncMock(return_value={}))
    monkeypatch.setattr(service, "_aggregate_logs", aggregate)

    out = await service.batch_usage_for_budget_windows([lookup], now=_WHEN)

    assert out[key] == QuotaUsageTotals(cost_usd=Decimal("0"), tokens=0, requests=0)
    aggregate.assert_not_awaited()


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
