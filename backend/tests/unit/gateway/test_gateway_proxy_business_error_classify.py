"""``classify_proxy_use_case_business_error`` 单测。"""

from __future__ import annotations

import httpx
from fastapi import status

from domains.gateway.domain.errors import (
    BudgetExceededError,
    GatewayModelNotFoundError,
    ModelNotAllowedError,
    RateLimitExceededError,
)
from domains.gateway.presentation.gateway_proxy_business_error_classify import (
    classify_proxy_use_case_business_error,
)
from libs.exceptions import ExternalServiceError, ValidationError


def test_classify_model_not_allowed() -> None:
    biz = classify_proxy_use_case_business_error(ModelNotAllowedError("gpt-99"))
    assert biz is not None
    assert biz.http_status == status.HTTP_400_BAD_REQUEST
    assert biz.openai_error_type == "model_not_allowed"
    assert biz.anthropic_error_type == "invalid_request_error"


def test_classify_gateway_model_not_found() -> None:
    biz = classify_proxy_use_case_business_error(
        GatewayModelNotFoundError("deepseek-v4-flash-260425")
    )
    assert biz is not None
    assert biz.http_status == status.HTTP_404_NOT_FOUND
    assert biz.openai_error_type == "model_not_found"
    assert biz.anthropic_error_type == "not_found_error"
    assert "deepseek-v4-flash-260425" in biz.message


def test_classify_router_model_miss_maps_404() -> None:
    exc = RuntimeError(
        "litellm.BadRequestError: no healthy deployments for model=foo"
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_404_NOT_FOUND
    assert biz.openai_error_type == "model_not_found"
    assert "Gateway 注册" in biz.message


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


def test_classify_validation_error_maps_400() -> None:
    biz = classify_proxy_use_case_business_error(
        ValidationError("Volcengine image endpoint id is required")
    )
    assert biz is not None
    assert biz.http_status == status.HTTP_400_BAD_REQUEST
    assert biz.openai_error_type == "invalid_request_error"


def test_classify_external_service_maps_502() -> None:
    biz = classify_proxy_use_case_business_error(
        ExternalServiceError("volcengine", message="upstream timeout")
    )
    assert biz is not None
    assert biz.http_status == status.HTTP_502_BAD_GATEWAY
    assert biz.openai_error_type == "api_error"


def test_classify_httpx_upstream_4xx_maps_400() -> None:
    response = httpx.Response(
        400,
        json={"error": {"message": "invalid model"}},
        request=httpx.Request("POST", "https://ark.cn-beijing.volces.com/api/v3/images/generations"),
    )
    exc = httpx.HTTPStatusError("bad", request=response.request, response=response)
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_400_BAD_REQUEST
    assert biz.message == "invalid model"
    assert biz.openai_error_type == "invalid_request_error"


def test_classify_httpx_upstream_5xx_maps_502() -> None:
    response = httpx.Response(
        503,
        request=httpx.Request("POST", "https://ark.cn-beijing.volces.com/api/v3/images/generations"),
    )
    exc = httpx.HTTPStatusError("bad", request=response.request, response=response)
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_502_BAD_GATEWAY
    assert biz.openai_error_type == "api_error"


def test_classify_unknown_returns_none() -> None:
    assert classify_proxy_use_case_business_error(RuntimeError("x")) is None
