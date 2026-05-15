"""OpenAI 兼容路由：将 ``ProxyUseCase`` 业务域异常映射为 OpenAI 形 HTTP 响应。"""

from __future__ import annotations

from fastapi import HTTPException, status

from domains.gateway.presentation.gateway_proxy_business_error_classify import (
    classify_proxy_use_case_business_error,
)


def openai_http_exception_from_proxy_business_error(exc: Exception) -> HTTPException:
    """把 ``ProxyUseCase`` 及校验链上的领域/值错误转为 ``detail={error:{type,message}}``。"""
    classified = classify_proxy_use_case_business_error(exc)
    if classified is not None:
        headers = (
            {"Retry-After": str(classified.retry_after)}
            if classified.retry_after is not None
            else None
        )
        return HTTPException(
            status_code=classified.http_status,
            detail={
                "error": {
                    "type": classified.openai_error_type,
                    "message": classified.message,
                }
            },
            headers=headers,
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": {"type": "server_error", "message": str(exc)}},
    )


__all__ = ["openai_http_exception_from_proxy_business_error"]
