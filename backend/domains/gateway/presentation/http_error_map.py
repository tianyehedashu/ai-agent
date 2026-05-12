"""将 Gateway 领域异常映射为 HTTP 响应（仅 Presentation 层使用）"""

from __future__ import annotations

from fastapi import HTTPException, status

from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
    NoPersonalTeamForProxyError,
    PersonalTeamNotInitializedError,
    TeamNotFoundError,
    TeamPermissionDeniedError,
    VirtualKeyInvalidError,
    VirtualKeyNotFoundError,
)


def http_exception_from_gateway_domain(exc: Exception) -> HTTPException:
    if isinstance(exc, VirtualKeyInvalidError):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    if isinstance(exc, NoPersonalTeamForProxyError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, (TeamNotFoundError, VirtualKeyNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (CredentialNotFoundError, ManagementEntityNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, TeamPermissionDeniedError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, PersonalTeamNotInitializedError):
        return HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


__all__ = ["http_exception_from_gateway_domain"]
