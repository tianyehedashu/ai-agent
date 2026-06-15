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
from domains.gateway.domain.proxy_policy import (
    is_router_deployment_cooldown,
    is_router_model_miss,
    is_router_unavailable_wrapper,
    resolve_upstream_proxy_exception,
    router_cooldown_retry_after,
    upstream_exception_http_status,
    upstream_exception_retry_after,
)
from libs.exceptions import ExternalServiceError, ValidationError


@dataclass(frozen=True)
class ProxyUseCaseBusinessFailure:
    """路由层可映射的失败描述（与具体 SDK 响应形无关）。"""

    http_status: int
    message: str
    openai_error_type: str
    anthropic_error_type: str
    retry_after: int | None = None


@dataclass(frozen=True)
class _UpstreamStatusMapping:
    """上游 HTTP 状态码到 OpenAI / Anthropic error type 的稳定映射。"""

    openai_error_type: str
    anthropic_error_type: str
    http_status: int | None = None  # None = 透传上游 status_code


# 仅覆盖网关需要原样透传语义的状态码；429 走 _upstream_rate_limit_failure，5xx 统一收敛 502。
_UPSTREAM_STATUS_MAP: dict[int, _UpstreamStatusMapping] = {
    400: _UpstreamStatusMapping("invalid_request_error", "invalid_request_error"),
    401: _UpstreamStatusMapping("authentication_error", "authentication_error"),
    403: _UpstreamStatusMapping("permission_error", "permission_error"),
    404: _UpstreamStatusMapping("model_not_found", "not_found_error"),
    408: _UpstreamStatusMapping("timeout", "api_error"),
    413: _UpstreamStatusMapping("request_too_large", "request_too_large"),
    422: _UpstreamStatusMapping("invalid_request_error", "invalid_request_error"),
}


def _extract_upstream_message(exc: Exception) -> str:
    """取上游异常的人类可读 message，去除 ``litellm.`` 前缀。"""
    raw = getattr(exc, "message", None)
    if isinstance(raw, str) and raw.strip():
        msg = raw.strip()
        if msg.startswith("litellm."):
            prefix_end = msg.find(": ")
            if prefix_end >= 0:
                msg = msg[prefix_end + 2 :].strip()
        return msg
    return str(exc)


def _upstream_rate_limit_failure(
    exc: Exception,
    *,
    retry_after: int | None = None,
) -> ProxyUseCaseBusinessFailure:
    return ProxyUseCaseBusinessFailure(
        http_status=status.HTTP_429_TOO_MANY_REQUESTS,
        message=_extract_upstream_message(exc),
        openai_error_type="rate_limit_exceeded",
        anthropic_error_type="rate_limit_error",
        retry_after=retry_after,
    )


def _classify_by_upstream_status(
    exc: Exception, upstream_status: int
) -> ProxyUseCaseBusinessFailure | None:
    """按上游真实 HTTP 状态码分流，避免被 Router cooldown 装饰吞噬原始语义。

    覆盖：401/403/404/408/413/422 透传；429 走限流；5xx 收敛为 502。
    其余状态码返回 ``None`` 让后续分支兜底。
    """
    if upstream_status == status.HTTP_429_TOO_MANY_REQUESTS:
        return _upstream_rate_limit_failure(
            exc,
            retry_after=upstream_exception_retry_after(exc),
        )
    if upstream_status >= 500:
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_502_BAD_GATEWAY,
            message=_extract_upstream_message(exc),
            openai_error_type="api_error",
            anthropic_error_type="api_error",
        )
    mapping = _UPSTREAM_STATUS_MAP.get(upstream_status)
    if mapping is None:
        return None
    return ProxyUseCaseBusinessFailure(
        http_status=mapping.http_status or upstream_status,
        message=_extract_upstream_message(exc),
        openai_error_type=mapping.openai_error_type,
        anthropic_error_type=mapping.anthropic_error_type,
    )


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
    unwrapped = resolve_upstream_proxy_exception(exc)
    classify_exc = unwrapped if unwrapped is not None else exc
    # 优先按上游真实 status_code 分流；LiteLLM Router 会给原始异常 setattr ``cooldown_time``，
    # 若先走 cooldown 判定，401/403/404 等会被错误吞成 429。
    # 仅当 Router 包装异常自身携带泛化 ``400`` 且无更具体嵌套上游时，跳过按 400 透传。
    upstream_status = upstream_exception_http_status(classify_exc)
    if upstream_status is not None:
        skip_generic_router_400 = (
            classify_exc is exc
            and is_router_unavailable_wrapper(exc)
            and upstream_status == status.HTTP_400_BAD_REQUEST
        )
        if not skip_generic_router_400:
            failure = _classify_by_upstream_status(classify_exc, upstream_status)
            if failure is not None:
                return failure
    if is_router_deployment_cooldown(exc):
        retry_after = router_cooldown_retry_after(exc)
        message = (
            f"模型部署暂不可用（上游限流或冷却中），请在 {retry_after} 秒后重试"
            if retry_after is not None
            else "模型部署暂不可用（上游限流或冷却中），请稍后重试"
        )
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            message=message,
            openai_error_type="rate_limit_exceeded",
            anthropic_error_type="rate_limit_error",
            retry_after=retry_after,
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
        raw_status = exc.response.status_code
        message = str(exc)
        with suppress(Exception):
            body = exc.response.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict) and err.get("message"):
                    message = str(err["message"])
                elif body.get("message"):
                    message = str(body["message"])
        if raw_status == status.HTTP_429_TOO_MANY_REQUESTS:
            retry_after_raw = exc.response.headers.get("retry-after") if exc.response else None
            retry_after: int | None = None
            if retry_after_raw is not None:
                with suppress(ValueError):
                    retry_after = int(str(retry_after_raw).strip())
            return ProxyUseCaseBusinessFailure(
                http_status=status.HTTP_429_TOO_MANY_REQUESTS,
                message=message,
                openai_error_type="rate_limit_exceeded",
                anthropic_error_type="rate_limit_error",
                retry_after=retry_after,
            )
        if raw_status >= 500:
            return ProxyUseCaseBusinessFailure(
                http_status=status.HTTP_502_BAD_GATEWAY,
                message=message,
                openai_error_type="api_error",
                anthropic_error_type="api_error",
            )
        mapping = _UPSTREAM_STATUS_MAP.get(raw_status)
        if mapping is not None:
            return ProxyUseCaseBusinessFailure(
                http_status=mapping.http_status or raw_status,
                message=message,
                openai_error_type=mapping.openai_error_type,
                anthropic_error_type=mapping.anthropic_error_type,
            )
        return ProxyUseCaseBusinessFailure(
            http_status=status.HTTP_400_BAD_REQUEST,
            message=message,
            openai_error_type="invalid_request_error",
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
            message=("请求的模型未在 Gateway 注册或当前无可用部署，请检查凭据与模型配置是否仍有效"),
            openai_error_type="model_not_found",
            anthropic_error_type="not_found_error",
        )
    return None


__all__ = [
    "ProxyUseCaseBusinessFailure",
    "classify_proxy_use_case_business_error",
]
