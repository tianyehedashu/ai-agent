"""``ProxyUseCase`` 业务域异常分类（OpenAI / Anthropic 兼容路由共用）。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import status

from domains.gateway.domain.errors import (
    BudgetExceededError,
    CapabilityNotAllowedError,
    GuardrailBlockedError,
    ModelNotAllowedError,
    RateLimitExceededError,
)


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
    if isinstance(exc, GuardrailBlockedError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            openai_error_type="guardrail_blocked",
            anthropic_error_type="invalid_request_error",
        )
    if isinstance(exc, ValueError):
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=str(exc),
            openai_error_type="invalid_request",
            anthropic_error_type="invalid_request_error",
        )
    return None


__all__ = [
    "ProxyUseCaseBusinessFailure",
    "classify_proxy_use_case_business_error",
]
