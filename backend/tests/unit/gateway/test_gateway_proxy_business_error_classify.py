"""``classify_proxy_use_case_business_error`` 单测。"""

from __future__ import annotations

from fastapi import status

from domains.gateway.domain.errors import (
    BudgetExceededError,
    ModelNotAllowedError,
    RateLimitExceededError,
)
from domains.gateway.presentation.gateway_proxy_business_error_classify import (
    classify_proxy_use_case_business_error,
)


def test_classify_model_not_allowed() -> None:
    biz = classify_proxy_use_case_business_error(ModelNotAllowedError("gpt-99"))
    assert biz is not None
    assert biz.http_status == status.HTTP_400_BAD_REQUEST
    assert biz.openai_error_type == "model_not_allowed"
    assert biz.anthropic_error_type == "invalid_request_error"


def test_classify_rate_limit_maps_anthropic_rate_limit_error() -> None:
    biz = classify_proxy_use_case_business_error(
        RateLimitExceededError("vkey", retry_after=30)
    )
    assert biz is not None
    assert biz.http_status == status.HTTP_429_TOO_MANY_REQUESTS
    assert biz.openai_error_type == "rate_limit_exceeded"
    assert biz.anthropic_error_type == "rate_limit_error"
    assert biz.retry_after == 30


def test_classify_budget_maps_anthropic_api_error() -> None:
    biz = classify_proxy_use_case_business_error(
        BudgetExceededError("team", "daily", 10.0, 10.0)
    )
    assert biz is not None
    assert biz.http_status == status.HTTP_402_PAYMENT_REQUIRED
    assert biz.openai_error_type == "budget_exceeded"
    assert biz.anthropic_error_type == "api_error"


def test_classify_unknown_returns_none() -> None:
    assert classify_proxy_use_case_business_error(RuntimeError("x")) is None
