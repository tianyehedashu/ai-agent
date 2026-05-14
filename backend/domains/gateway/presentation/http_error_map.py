"""将 Gateway 领域异常映射为 HTTP 响应（仅 Presentation 层使用）"""

from __future__ import annotations

from fastapi import HTTPException, status

from domains.gateway.domain.errors import (
    CredentialInUseError,
    CredentialNameConflictError,
    CredentialNotFoundError,
    ManagementEntityNotFoundError,
    NoPersonalTeamForProxyError,
    VirtualKeyInvalidError,
    VirtualKeyNotFoundError,
)
from libs.iam.team_http import map_team_access_exception_to_http


def http_exception_from_gateway_domain(exc: Exception) -> HTTPException:
    team_http = map_team_access_exception_to_http(exc)
    if team_http is not None:
        return team_http
    if isinstance(exc, VirtualKeyInvalidError):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    if isinstance(exc, NoPersonalTeamForProxyError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, VirtualKeyNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (CredentialNotFoundError, ManagementEntityNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (CredentialInUseError, CredentialNameConflictError)):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


__all__ = ["http_exception_from_gateway_domain"]
