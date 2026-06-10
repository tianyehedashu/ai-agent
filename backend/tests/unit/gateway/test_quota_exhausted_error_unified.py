"""QuotaExhaustedError 统一错误体系单测。

验证：
1. 基类属性完整
2. 三个子类均正确继承并映射参数
3. 向后兼容属性（plan_id / cooldown_seconds / period）可用
4. retry_after 计算正确
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domains.gateway.domain.errors import (
    BudgetExceededError,
    EntitlementPlanExhaustedError,
    ProviderPlanExhaustedError,
    QuotaExhaustedError,
)


class TestQuotaExhaustedErrorBase:
    """基类行为"""

    def test_all_fields_preserved(self) -> None:
        exc = QuotaExhaustedError(
            layer="platform",
            scope="team_123",
            quota_label="daily",
            reason="usd",
            limit=100.0,
            used=80.0,
            retry_after=60,
        )
        assert exc.layer == "platform"
        assert exc.scope == "team_123"
        assert exc.quota_label == "daily"
        assert exc.reason == "usd"
        assert exc.limit == 100.0
        assert exc.used == 80.0
        assert exc.retry_after == 60
        assert "[platform] team_123/daily" in str(exc)
        assert "reason=usd" in str(exc)
        assert "限额" in str(exc)
        assert "已用" in str(exc)

    def test_optional_retry_after_defaults_none(self) -> None:
        exc = QuotaExhaustedError(
            layer="upstream",
            scope="plan_abc",
            quota_label="rolling",
            reason="requests",
            limit=0.0,
            used=0.0,
        )
        assert exc.retry_after is None


class TestBudgetExceededError:
    """平台预算错误向后兼容"""

    def test_inherits_quota_exhausted(self) -> None:
        exc = BudgetExceededError("tenant", "monthly", 500.0, 510.0)
        assert isinstance(exc, QuotaExhaustedError)

    def test_backward_compatible_scope_period(self) -> None:
        exc = BudgetExceededError("tenant", "monthly", 500.0, 510.0)
        assert exc.scope == "tenant"
        assert exc.period == "monthly"
        assert exc.quota_label == "monthly"
        assert exc.layer == "platform"
        assert exc.reason == "usd"
        assert exc.limit == 500.0
        assert exc.used == 510.0


class TestEntitlementPlanExhaustedError:
    """下游套餐错误向后兼容"""

    def test_inherits_quota_exhausted(self) -> None:
        exc = EntitlementPlanExhaustedError(
            plan_id="p1",
            quota_label="chat",
            reason="tokens",
        )
        assert isinstance(exc, QuotaExhaustedError)

    def test_backward_compatible_plan_id(self) -> None:
        exc = EntitlementPlanExhaustedError(
            plan_id="p1",
            quota_label="chat",
            reason="tokens",
        )
        assert exc.plan_id == "p1"
        assert exc.scope == "p1"

    def test_retry_at_parsed_to_retry_after(self) -> None:
        future = (datetime.now(UTC) + timedelta(seconds=120)).isoformat()
        exc = EntitlementPlanExhaustedError(
            plan_id="p1",
            quota_label="chat",
            reason="requests",
            retry_at=future,
        )
        assert exc.retry_after is not None
        assert exc.retry_after > 110  # 允许几秒容差
        assert exc.retry_after <= 125

    def test_invalid_retry_at_ignored(self) -> None:
        exc = EntitlementPlanExhaustedError(
            plan_id="p1",
            quota_label="chat",
            reason="requests",
            retry_at="not-a-date",
        )
        assert exc.retry_after is None

    def test_no_retry_at_means_none(self) -> None:
        exc = EntitlementPlanExhaustedError(
            plan_id="p1",
            quota_label="chat",
            reason="requests",
        )
        assert exc.retry_after is None


class TestProviderPlanExhaustedError:
    """上游套餐错误向后兼容"""

    def test_inherits_quota_exhausted(self) -> None:
        exc = ProviderPlanExhaustedError(
            plan_id="p2",
            quota_label="rpm",
            reason="requests",
            cooldown_seconds=86400,
        )
        assert isinstance(exc, QuotaExhaustedError)

    def test_backward_compatible_plan_id(self) -> None:
        exc = ProviderPlanExhaustedError(
            plan_id="p2",
            quota_label="rpm",
            reason="requests",
            cooldown_seconds=86400,
        )
        assert exc.plan_id == "p2"
        assert exc.scope == "p2"

    def test_backward_compatible_cooldown_seconds(self) -> None:
        exc = ProviderPlanExhaustedError(
            plan_id="p2",
            quota_label="rpm",
            reason="requests",
            cooldown_seconds=86400,
        )
        assert exc.cooldown_seconds == 86400
        assert exc.retry_after == 86400

    def test_cooldown_seconds_zero_when_no_retry_after(self) -> None:
        exc = ProviderPlanExhaustedError(
            plan_id="p2",
            quota_label="rpm",
            reason="requests",
            cooldown_seconds=0,
        )
        assert exc.cooldown_seconds == 0
        assert exc.retry_after == 0


class TestPolymorphism:
    """多态捕获：基类可捕获所有子类"""

    @pytest.mark.parametrize(
        "exc",
        [
            BudgetExceededError("t", "d", 1.0, 2.0),
            EntitlementPlanExhaustedError(plan_id="p", quota_label="q", reason="r"),
            ProviderPlanExhaustedError(
                plan_id="p", quota_label="q", reason="r", cooldown_seconds=10
            ),
        ],
    )
    def test_all_caught_by_base_class(self, exc: QuotaExhaustedError) -> None:
        assert isinstance(exc, QuotaExhaustedError)
        assert hasattr(exc, "layer")
        assert hasattr(exc, "scope")
        assert hasattr(exc, "quota_label")
        assert hasattr(exc, "reason")
        assert hasattr(exc, "limit")
        assert hasattr(exc, "used")
