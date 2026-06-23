"""请求日志失败状态分类：异常 → RequestStatus + 稳定 error_code。"""

from __future__ import annotations

from dataclasses import dataclass

from domains.gateway.domain.errors import (
    BudgetExceededError,
    EntitlementPlanExhaustedError,
    GuardrailBlockedError,
    ProviderPlanExhaustedError,
    QuotaExhaustedError,
    RateLimitExceededError,
)
from domains.gateway.domain.types import RequestStatus
from domains.gateway.presentation.gateway_proxy_business_error_classify import (
    classify_proxy_use_case_business_error,
)

_BUDGET_ERROR_CODES: frozenset[str] = frozenset(
    {
        "budget_exceeded",
        "entitlement_exhausted",
        "upstream_quota_exhausted",
    }
)
_RATE_LIMIT_ERROR_CODES: frozenset[str] = frozenset({"rate_limit_exceeded", "rate_limit_error"})
_GUARDRAIL_ERROR_CODES: frozenset[str] = frozenset({"guardrail_blocked"})

_UPSTREAM_QUOTA_KEYWORDS: tuple[str, ...] = (
    "insufficient_quota",
    "quota_exceeded",
    "quota exceeded",
    "rate_limit_exceeded",
    "resource_exhausted",
    "resource has been exhausted",
    "you exceeded your current quota",
    "billing_hard_limit_reached",
    "exceeded_call_rate_limit",
)


@dataclass(frozen=True, slots=True)
class ClassifiedRequestLogFailure:
    """单次失败落库用的 status / error_code / error_message。"""

    status: RequestStatus
    error_code: str
    error_message: str


def _extract_status_code(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    code = getattr(exc, "http_status", None)
    if isinstance(code, int):
        return code
    return None


def _is_upstream_quota_exhaustion(
    *, error_code: str | None, error_message: str | None, status_code: int | None
) -> bool:
    if status_code is not None and status_code in (402, 429):
        msg = (error_message or "").lower()
        for kw in _UPSTREAM_QUOTA_KEYWORDS:
            if kw in msg:
                return True
        if status_code == 402:
            return True
    if error_code is None and error_message is None:
        return False
    blob = f"{error_code or ''} {error_message or ''}".lower()
    return any(kw in blob for kw in _UPSTREAM_QUOTA_KEYWORDS)


def _quota_error_code(exc: QuotaExhaustedError) -> str:
    if isinstance(exc, EntitlementPlanExhaustedError):
        return "entitlement_exhausted"
    if isinstance(exc, ProviderPlanExhaustedError):
        return "upstream_quota_exhausted"
    if isinstance(exc, BudgetExceededError):
        return "budget_exceeded"
    return "budget_exceeded"


def _status_from_error_code(error_code: str) -> RequestStatus:
    if error_code in _BUDGET_ERROR_CODES:
        return RequestStatus.BUDGET_EXCEEDED
    if error_code in _RATE_LIMIT_ERROR_CODES:
        return RequestStatus.RATE_LIMITED
    if error_code in _GUARDRAIL_ERROR_CODES:
        return RequestStatus.GUARDRAIL_BLOCKED
    return RequestStatus.FAILED


def classify_request_log_failure(exc: BaseException) -> ClassifiedRequestLogFailure:
    """把代理链路上的异常映射为 request log 的 status 与稳定 error_code。"""
    message = str(exc)

    if isinstance(exc, QuotaExhaustedError):
        error_code = _quota_error_code(exc)
        return ClassifiedRequestLogFailure(
            status=RequestStatus.BUDGET_EXCEEDED,
            error_code=error_code,
            error_message=message,
        )
    if isinstance(exc, RateLimitExceededError):
        return ClassifiedRequestLogFailure(
            status=RequestStatus.RATE_LIMITED,
            error_code="rate_limit_exceeded",
            error_message=message,
        )
    if isinstance(exc, GuardrailBlockedError):
        return ClassifiedRequestLogFailure(
            status=RequestStatus.GUARDRAIL_BLOCKED,
            error_code="guardrail_blocked",
            error_message=message,
        )

    classified = classify_proxy_use_case_business_error(exc)
    if classified is not None:
        error_code = classified.openai_error_type
        if _is_upstream_quota_exhaustion(
            error_code=type(exc).__name__,
            error_message=message,
            status_code=_extract_status_code(exc),
        ) and error_code not in _BUDGET_ERROR_CODES:
            error_code = "upstream_quota_exhausted"
        return ClassifiedRequestLogFailure(
            status=_status_from_error_code(error_code),
            error_code=error_code,
            error_message=classified.message,
        )

    exc_name = type(exc).__name__
    if _is_upstream_quota_exhaustion(
        error_code=exc_name,
        error_message=message,
        status_code=_extract_status_code(exc),
    ):
        return ClassifiedRequestLogFailure(
            status=RequestStatus.BUDGET_EXCEEDED,
            error_code="upstream_quota_exhausted",
            error_message=message,
        )

    return ClassifiedRequestLogFailure(
        status=RequestStatus.FAILED,
        error_code=exc_name,
        error_message=message,
    )


__all__ = ["ClassifiedRequestLogFailure", "classify_request_log_failure"]
