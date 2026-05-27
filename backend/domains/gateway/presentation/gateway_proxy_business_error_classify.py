"""``ProxyUseCase`` 业务域异常分类（OpenAI / Anthropic 兼容路由共用）。"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

from fastapi import status
import httpx

from domains.gateway.domain.errors import (
    BudgetExceededError,
    CapabilityNotAllowedError,
    EntitlementPlanExhaustedError,
    GatewayModelNotFoundError,
    GuardrailBlockedError,
    InvocationPolicyViolationError,
    ModelNotAllowedError,
    RateLimitExceededError,
)
from domains.gateway.domain.proxy_policy import is_router_model_miss
from libs.exceptions import ExternalServiceError, ValidationError


@dataclass(frozen=True)
class ProxyUseCaseBusinessFailure:
    """路由层可映射的失败描述（与具体 SDK 响应形无关）。"""

    http_status: int
    message: str
    openai_error_type: str
    anthropic_error_type: str
    retry_after: int | None = None


def classify_proxy_use_case_business_error(exc: Exception) -> ProxyUseCaseBusinessFailure | None:
    """识别 ``ProxyUseCase`` 及前置校验抛出的可映射业务/值错误；未识别则返回 ``None``。"""
    if isinstance(exc, ModelNotAllowedError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            openai_error_type="model_not_allowed",
            anthropic_error_type="invalid_request_error",
        )
    if isinstance(exc, GatewayModelNotFoundError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_404_NOT_FOUND,
            message=str(exc),
            openai_error_type="model_not_found",
            anthropic_error_type="not_found_error",
        )
    if isinstance(exc, CapabilityNotAllowedError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            openai_error_type="capability_not_allowed",
            anthropic_error_type="invalid_request_error",
        )
    if isinstance(exc, RateLimitExceededError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            message=str(exc),
            openai_error_type="rate_limit_exceeded",
            anthropic_error_type="rate_limit_error",
            retry_after=exc.retry_after,
        )
    if isinstance(exc, BudgetExceededError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_402_PAYMENT_REQUIRED,
            message=str(exc),
            openai_error_type="budget_exceeded",
            anthropic_error_type="api_error",
        )
    if isinstance(exc, EntitlementPlanExhaustedError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            message=str(exc),
            openai_error_type="entitlement_exhausted",
            anthropic_error_type="rate_limit_error",
        )
    if isinstance(exc, GuardrailBlockedError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            openai_error_type="guardrail_blocked",
            anthropic_error_type="invalid_request_error",
        )
    if isinstance(exc, InvocationPolicyViolationError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            openai_error_type="invocation_policy_violation",
            anthropic_error_type="invalid_request_error",
        )
    if isinstance(exc, ValidationError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            openai_error_type="invalid_request_error",
            anthropic_error_type="invalid_request_error",
        )
    if isinstance(exc, ExternalServiceError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_502_BAD_GATEWAY,
            message=str(exc),
            openai_error_type="api_error",
            anthropic_error_type="api_error",
        )
    if isinstance(exc, httpx.HTTPStatusError):
        upstream_status = exc.response.status_code
        http_status = (
            status.HTTP_502_BAD_GATEWAY
            if upstream_status >= 500
            else status.HTTP_400_BAD_REQUEST
        )
        message = str(exc)
        with suppress(Exception):
            body = exc.response.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict) and err.get("message"):
                    message = str(err["message"])
                elif body.get("message"):
                    message = str(body["message"])
        return ProxyUseCaseBusinessFailure(
            http_status=http_status,
            message=message,
            openai_error_type="api_error" if upstream_status >= 500 else "invalid_request_error",
            anthropic_error_type="api_error",
        )
    if isinstance(exc, ValueError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            openai_error_type="invalid_request",
            anthropic_error_type="invalid_request_error",
        )
    if is_router_model_miss(exc):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_404_NOT_FOUND,
            message=(
                "请求的模型未在 Gateway 注册或当前无可用部署，"
                "请检查凭据与模型配置是否仍有效"
            ),
            openai_error_type="model_not_found",
            anthropic_error_type="not_found_error",
        )
    return None


__all__ = [
    "ProxyUseCaseBusinessFailure",
    "classify_proxy_use_case_business_error",
]
