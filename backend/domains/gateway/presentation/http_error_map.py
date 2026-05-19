"""将 Gateway 领域异常映射为 HTTP 响应（仅 Presentation 层使用）

适用范围：管理 API 路由（``management_router`` / proxy 鉴权 deps）。
ProxyUseCase 业务错误另由 ``gateway_proxy_business_error_classify`` 转换为 SDK 兼容载荷。
"""

from __future__ import annotations

from fastapi import HTTPException, status

from domains.gateway.domain.errors import (
    ApiKeyGatewayGrantDeniedError,
    ApiKeyGatewayGrantRequiredError,
    CredentialApiKeyDecryptError,
    CredentialNameConflictError,
    CredentialNotFoundError,
    EntitlementPlanExhaustedError,
    GatewayTeamHeaderInvalidError,
    GatewayTeamHeaderRequiredError,
    ManagementEntityNotFoundError,
    NoPersonalTeamForProxyError,
    PlatformApiKeyInvalidError,
    PlatformApiKeyMissingGatewayProxyScopeError,
    SystemCredentialAdminRequiredError,
    SystemVirtualKeyForbiddenError,
    VirtualKeyDecryptError,
    VirtualKeyInvalidError,
    VirtualKeyNotFoundError,
)
from libs.iam.team_http import map_team_access_exception_to_http


def _http_exception_for_gateway_domain(exc: Exception) -> HTTPException | None:
    """将已知的 Gateway 领域异常映射为 ``HTTPException``；未知类型返回 ``None``。"""
    if isinstance(exc, (VirtualKeyInvalidError, PlatformApiKeyInvalidError)):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    if isinstance(exc, PlatformApiKeyMissingGatewayProxyScopeError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, NoPersonalTeamForProxyError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, (GatewayTeamHeaderInvalidError, GatewayTeamHeaderRequiredError)):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, (ApiKeyGatewayGrantDeniedError, ApiKeyGatewayGrantRequiredError)):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, VirtualKeyNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, SystemVirtualKeyForbiddenError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, (CredentialApiKeyDecryptError, VirtualKeyDecryptError)):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, (CredentialNotFoundError, ManagementEntityNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, CredentialNameConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, SystemCredentialAdminRequiredError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, EntitlementPlanExhaustedError):
        headers: dict[str, str] = {}
        if exc.retry_at:
            headers["X-Plan-Retry-At"] = exc.retry_at
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "gateway/entitlement_exhausted",
                "message": str(exc),
                "plan_id": exc.plan_id,
                "quota_label": exc.quota_label,
                "reason": exc.reason,
                "retry_at": exc.retry_at,
            },
            headers=headers or None,
        )
    return None


def http_exception_from_gateway_domain(exc: Exception) -> HTTPException:
    team_http = map_team_access_exception_to_http(exc)
    if team_http is not None:
        return team_http
    mapped = _http_exception_for_gateway_domain(exc)
    if mapped is not None:
        return mapped
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


__all__ = ["http_exception_from_gateway_domain"]
