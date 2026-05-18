"""Provider/Entitlement Plan 周期重置策略单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid

import pytest

from domains.gateway.domain.quota_plan import (
    PlanQuotaSnapshot,
    PlanQuotaSpec,
    compute_minute_index,
    compute_reset_at,
    compute_window_start_minute,
)
from domains.gateway.infrastructure.callbacks.custom_logger import (
    _is_upstream_quota_exhaustion,
)


@pytest.mark.unit
class TestQuotaPlanResetStrategy:
    def test_calendar_daily_utc_uses_current_utc_day_boundary(self) -> None:
        now = datetime(2026, 5, 18, 11, 20, tzinfo=UTC)

        assert compute_window_start_minute(
            now,
            86400,
            strategy="calendar_daily_utc",
        ) == compute_minute_index(datetime(2026, 5, 18, tzinfo=UTC))
        assert compute_reset_at(
            strategy="calendar_daily_utc",
            window_seconds=86400,
            now=now,
        ) == datetime(2026, 5, 19, tzinfo=UTC)

    def test_calendar_monthly_utc_uses_current_month_boundary(self) -> None:
        now = datetime(2026, 12, 18, 11, 20, tzinfo=UTC)

        assert compute_window_start_minute(
            now,
            86400 * 31,
            strategy="calendar_monthly_utc",
        ) == compute_minute_index(datetime(2026, 12, 1, tzinfo=UTC))
        assert compute_reset_at(
            strategy="calendar_monthly_utc",
            window_seconds=86400 * 31,
            now=now,
        ) == datetime(2027, 1, 1, tzinfo=UTC)

    def test_plan_anniversary_uses_valid_from_as_anchor(self) -> None:
        valid_from = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
        now = valid_from + timedelta(days=10, hours=2)
        window_seconds = 7 * 86400

        assert compute_window_start_minute(
            now,
            window_seconds,
            strategy="plan_anniversary",
            plan_valid_from=valid_from,
        ) == compute_minute_index(valid_from + timedelta(days=7))
        assert compute_reset_at(
            strategy="plan_anniversary",
            window_seconds=window_seconds,
            now=now,
            plan_valid_from=valid_from,
        ) == valid_from + timedelta(days=14)

    def test_snapshot_reset_at_delegates_strategy(self) -> None:
        now = datetime(2026, 5, 18, 11, 20, tzinfo=UTC)
        spec = PlanQuotaSpec(
            quota_id=uuid.uuid4(),
            label="daily",
            window_seconds=86400,
            limit_usd=Decimal("1"),
            reset_strategy="calendar_daily_utc",
        )
        snap = PlanQuotaSnapshot(spec=spec, exhausted_reason="usd")

        assert snap.reset_at(now) == datetime(2026, 5, 19, tzinfo=UTC)


@pytest.mark.unit
class TestUpstreamQuotaSignal:
    def test_detects_insufficient_quota_429(self) -> None:
        assert _is_upstream_quota_exhaustion(
            error_code="RateLimitError",
            error_message="insufficient_quota: You exceeded your current quota",
            status_code=429,
        )

    def test_detects_resource_exhausted_without_status_code(self) -> None:
        assert _is_upstream_quota_exhaustion(
            error_code="ResourceExhausted",
            error_message="RESOURCE_EXHAUSTED",
            status_code=None,
        )

    def test_plain_rate_limit_429_is_not_forced_exhaustion(self) -> None:
        assert not _is_upstream_quota_exhaustion(
            error_code="RateLimitError",
            error_message="too many requests, retry later",
            status_code=429,
        )

