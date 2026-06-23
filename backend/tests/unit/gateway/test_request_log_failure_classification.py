"""request_log_failure_classification 单测。"""

from __future__ import annotations

from domains.gateway.application.request_log_failure_classification import (
    classify_request_log_failure,
)
from domains.gateway.domain.errors import (
    BudgetExceededError,
    EntitlementPlanExhaustedError,
    GuardrailBlockedError,
    RateLimitExceededError,
)
from domains.gateway.domain.types import RequestStatus


def test_classify_budget_exceeded() -> None:
    exc = BudgetExceededError(scope="team", period="daily", limit=10.0, used=10.0)
    classified = classify_request_log_failure(exc)
    assert classified.status == RequestStatus.BUDGET_EXCEEDED
    assert classified.error_code == "budget_exceeded"


def test_classify_entitlement_exhausted() -> None:
    exc = EntitlementPlanExhaustedError(
        plan_id="plan-1",
        quota_label="daily",
        reason="requests",
    )
    classified = classify_request_log_failure(exc)
    assert classified.status == RequestStatus.BUDGET_EXCEEDED
    assert classified.error_code == "entitlement_exhausted"


def test_classify_rate_limit_exceeded() -> None:
    exc = RateLimitExceededError("rpm", retry_after=30)
    classified = classify_request_log_failure(exc)
    assert classified.status == RequestStatus.RATE_LIMITED
    assert classified.error_code == "rate_limit_exceeded"


def test_classify_guardrail_blocked() -> None:
    exc = GuardrailBlockedError("pii detected")
    classified = classify_request_log_failure(exc)
    assert classified.status == RequestStatus.GUARDRAIL_BLOCKED
    assert classified.error_code == "guardrail_blocked"


def test_classify_generic_exception() -> None:
    exc = RuntimeError("upstream timeout")
    classified = classify_request_log_failure(exc)
    assert classified.status == RequestStatus.FAILED
    assert classified.error_code == "RuntimeError"


def test_classify_upstream_quota_keywords() -> None:
    class _QuotaError(Exception):
        status_code = 402

        def __str__(self) -> str:
            return "insufficient_quota: billing hard limit reached"

    classified = classify_request_log_failure(_QuotaError())
    assert classified.status == RequestStatus.BUDGET_EXCEEDED
    assert classified.error_code == "upstream_quota_exhausted"
