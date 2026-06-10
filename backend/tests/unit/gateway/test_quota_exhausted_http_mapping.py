"""配额耗尽错误 HTTP 映射单测。

验证统一映射后：
1. 所有子类均映射为 429
2. Retry-After 头按 retry_after 设置
3. extra 包含 layer / scope / quota_label / reason / limit / used
"""

from __future__ import annotations

from fastapi import status

from domains.gateway.domain.errors import (
    BudgetExceededError,
    EntitlementPlanExhaustedError,
    ProviderPlanExhaustedError,
    QuotaExhaustedError,
)
from domains.gateway.presentation.http_error_map import problem_context_from_gateway_domain


class TestQuotaExhaustedHttpMapping:
    """统一映射行为"""

    def test_base_class_maps_429(self) -> None:
        exc = QuotaExhaustedError(
            layer="platform",
            scope="team_1",
            quota_label="daily",
            reason="usd",
            limit=100.0,
            used=100.0,
            retry_after=30,
        )
        ctx = problem_context_from_gateway_domain(exc)
        assert ctx.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert ctx.code == "GATEWAY_ENTITLEMENT_EXHAUSTED"
        assert ctx.headers is not None
        assert ctx.headers.get("Retry-After") == "30"

    def test_budget_exceeded_maps_429(self) -> None:
        exc = BudgetExceededError("team", "monthly", 500.0, 510.0)
        ctx = problem_context_from_gateway_domain(exc)
        assert ctx.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert ctx.headers is None  # retry_after 为 None

    def test_entitlement_exhausted_maps_429_with_retry_after(self) -> None:
        exc = EntitlementPlanExhaustedError(
            plan_id="p1",
            quota_label="chat",
            reason="tokens",
            retry_at="2099-01-01T00:00:00+00:00",
        )
        ctx = problem_context_from_gateway_domain(exc)
        assert ctx.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert ctx.code == "GATEWAY_ENTITLEMENT_EXHAUSTED"
        assert ctx.headers is not None
        assert "Retry-After" in ctx.headers
        assert int(ctx.headers["Retry-After"]) > 0

    def test_provider_plan_exhausted_maps_429_with_retry_after(self) -> None:
        exc = ProviderPlanExhaustedError(
            plan_id="p2",
            quota_label="rpm",
            reason="requests",
            cooldown_seconds=3600,
        )
        ctx = problem_context_from_gateway_domain(exc)
        assert ctx.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert ctx.headers is not None
        assert ctx.headers.get("Retry-After") == "3600"

    def test_extra_fields_populated(self) -> None:
        exc = QuotaExhaustedError(
            layer="upstream",
            scope="plan_2",
            quota_label="rolling",
            reason="requests",
            limit=1000.0,
            used=1001.0,
            retry_after=60,
        )
        ctx = problem_context_from_gateway_domain(exc)
        assert ctx.extra is not None
        assert ctx.extra["layer"] == "upstream"
        assert ctx.extra["scope"] == "plan_2"
        assert ctx.extra["quota_label"] == "rolling"
        assert ctx.extra["reason"] == "requests"
        assert ctx.extra["limit"] == 1000.0
        assert ctx.extra["used"] == 1001.0
        assert ctx.extra["retry_after"] == 60

    def test_zero_retry_after_no_header(self) -> None:
        exc = ProviderPlanExhaustedError(
            plan_id="p2",
            quota_label="rpm",
            reason="requests",
            cooldown_seconds=0,
        )
        ctx = problem_context_from_gateway_domain(exc)
        assert ctx.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        # cooldown_seconds=0 时 retry_after=0，不满足 >0 条件，无 header
        assert ctx.headers is None or ctx.headers.get("Retry-After") is None
