"""``classify_proxy_use_case_business_error`` 单测。"""

from __future__ import annotations

from fastapi import status
import httpx

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


def test_classify_gateway_model_not_found_with_team_label() -> None:
    biz = classify_proxy_use_case_business_error(GatewayModelNotFoundError("m1", team_label="研发"))
    assert biz is not None
    assert "当前调用团队: 研发" in biz.message


def test_classify_router_model_miss_maps_404() -> None:
    exc = RuntimeError("litellm.BadRequestError: no healthy deployments for model=foo")
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_404_NOT_FOUND
    assert biz.openai_error_type == "model_not_found"
    assert "Gateway 注册" in biz.message


def test_classify_rate_limit_maps_anthropic_rate_limit_error() -> None:
    biz = classify_proxy_use_case_business_error(RateLimitExceededError("vkey", retry_after=30))
    assert biz is not None
    assert biz.http_status == status.HTTP_429_TOO_MANY_REQUESTS
    assert biz.openai_error_type == "rate_limit_exceeded"
    assert biz.anthropic_error_type == "rate_limit_error"
    assert biz.retry_after == 30


def test_classify_budget_maps_anthropic_api_error() -> None:
    biz = classify_proxy_use_case_business_error(BudgetExceededError("team", "daily", 10.0, 10.0))
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
        request=httpx.Request(
            "POST", "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        ),
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
        request=httpx.Request(
            "POST", "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        ),
    )
    exc = httpx.HTTPStatusError("bad", request=response.request, response=response)
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_502_BAD_GATEWAY
    assert biz.openai_error_type == "api_error"


def test_classify_unknown_returns_none() -> None:
    assert classify_proxy_use_case_business_error(RuntimeError("x")) is None


def test_classify_router_cooldown_maps_429() -> None:
    from litellm.types.router import RouterRateLimitError

    exc = RouterRateLimitError(
        model="gw/t/x/deepseek",
        cooldown_time=60,
        enable_pre_call_checks=True,
        cooldown_list=["dep-1"],
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_429_TOO_MANY_REQUESTS
    assert biz.openai_error_type == "rate_limit_exceeded"
    assert biz.anthropic_error_type == "rate_limit_error"
    assert biz.retry_after == 60
    assert "60 秒后重试" in biz.message


def test_classify_litellm_upstream_rate_limit_maps_429() -> None:
    import litellm

    exc = litellm.RateLimitError(
        message="Volcengine rate limit exceeded",
        llm_provider="volcengine",
        model="deepseek-v4",
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_429_TOO_MANY_REQUESTS
    assert biz.openai_error_type == "rate_limit_exceeded"
    assert biz.anthropic_error_type == "rate_limit_error"
    assert "Volcengine rate limit exceeded" in biz.message


def test_classify_litellm_upstream_authentication_maps_401() -> None:
    """上游 401 凭据失效必须透传 401，不能被后续 cooldown / 502 分支吞掉。"""
    import litellm

    exc = litellm.AuthenticationError(
        message="Invalid API key for cmecloud",
        llm_provider="cmecloud",
        model="claude-sonnet-4.5",
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_401_UNAUTHORIZED
    assert biz.openai_error_type == "authentication_error"
    assert biz.anthropic_error_type == "authentication_error"
    assert "Invalid API key for cmecloud" in biz.message
    assert biz.retry_after is None


def test_classify_litellm_authentication_with_cooldown_time_still_maps_401() -> None:
    """LiteLLM Router 会给原始异常 setattr ``cooldown_time``；401 仍须优先于 cooldown 路径。"""
    import litellm

    exc = litellm.AuthenticationError(
        message="401 Unauthorized",
        llm_provider="openai",
        model="gpt-4o",
    )
    exc.cooldown_time = 60  # type: ignore[attr-defined]
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_401_UNAUTHORIZED
    assert biz.openai_error_type == "authentication_error"


def test_classify_litellm_permission_maps_403() -> None:
    import litellm

    response = httpx.Response(
        403,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    exc = litellm.PermissionDeniedError(
        message="Region not permitted",
        llm_provider="openai",
        model="gpt-4o",
        response=response,
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_403_FORBIDDEN
    assert biz.openai_error_type == "permission_error"
    assert biz.anthropic_error_type == "permission_error"


def test_classify_litellm_not_found_maps_404() -> None:
    import litellm

    exc = litellm.NotFoundError(
        message="model deepseek-x not found upstream",
        llm_provider="openai",
        model="deepseek-x",
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_404_NOT_FOUND
    assert biz.openai_error_type == "model_not_found"
    assert biz.anthropic_error_type == "not_found_error"


def test_classify_litellm_timeout_maps_408() -> None:
    import litellm

    exc = litellm.Timeout(
        message="upstream timeout after 30s",
        llm_provider="openai",
        model="gpt-4o",
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_408_REQUEST_TIMEOUT
    assert biz.openai_error_type == "timeout"
    assert biz.anthropic_error_type == "api_error"


def test_classify_litellm_unprocessable_maps_422() -> None:
    import litellm

    response = httpx.Response(
        422,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    exc = litellm.UnprocessableEntityError(
        message="messages.0.content: invalid type",
        llm_provider="openai",
        model="gpt-4o",
        response=response,
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert biz.openai_error_type == "invalid_request_error"
    assert biz.anthropic_error_type == "invalid_request_error"


def test_classify_litellm_internal_5xx_collapses_to_502() -> None:
    import litellm

    exc = litellm.InternalServerError(
        message="upstream 503",
        llm_provider="openai",
        model="gpt-4o",
    )
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_502_BAD_GATEWAY
    assert biz.openai_error_type == "api_error"
    assert biz.anthropic_error_type == "api_error"


def test_classify_httpx_upstream_401_maps_401() -> None:
    response = httpx.Response(
        401,
        json={"error": {"message": "invalid api key"}},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    exc = httpx.HTTPStatusError("unauthorized", request=response.request, response=response)
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_401_UNAUTHORIZED
    assert biz.openai_error_type == "authentication_error"
    assert biz.message == "invalid api key"


def test_classify_httpx_upstream_429_maps_429_with_retry_after() -> None:
    response = httpx.Response(
        429,
        headers={"Retry-After": "15"},
        json={"error": {"message": "too many requests"}},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    exc = httpx.HTTPStatusError("rate limited", request=response.request, response=response)
    biz = classify_proxy_use_case_business_error(exc)
    assert biz is not None
    assert biz.http_status == status.HTTP_429_TOO_MANY_REQUESTS
    assert biz.openai_error_type == "rate_limit_exceeded"
    assert biz.retry_after == 15
