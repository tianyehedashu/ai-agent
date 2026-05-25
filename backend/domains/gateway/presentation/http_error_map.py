"""将 Gateway / 团队领域异常映射为 RFC 7807 ProblemContext（Presentation 层）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi import status

from domains.gateway.domain.errors import (
    ApiKeyGatewayGrantDeniedError,
    ApiKeyGatewayGrantRequiredError,
    CredentialApiKeyDecryptError,
    CredentialNameConflictError,
    CredentialNotFoundError,
    EntitlementPlanExhaustedError,
    GatewayTeamHeaderInvalidError,
    GatewayTeamHeaderRequiredError,
    GatewayVkeyTeamHeaderMismatchError,
    InvalidSystemVisibilityError,
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
from libs.api.problem_details import ProblemContext, default_title_for_status
from libs.exceptions import PermissionDeniedError
from libs.exceptions.codes import (
    API_KEY_GATEWAY_GRANT_DENIED,
    API_KEY_GATEWAY_GRANT_REQUIRED,
    CREDENTIAL_API_KEY_DECRYPT_ERROR,
    CREDENTIAL_NAME_CONFLICT,
    CREDENTIAL_NOT_FOUND,
    GATEWAY_DOMAIN_ERROR,
    GATEWAY_ENTITLEMENT_EXHAUSTED,
    GATEWAY_TEAM_HEADER_INVALID,
    GATEWAY_TEAM_HEADER_REQUIRED,
    GATEWAY_VKEY_TEAM_HEADER_MISMATCH,
    INVALID_SYSTEM_VISIBILITY,
    MANAGEMENT_ENTITY_NOT_FOUND,
    NO_PERSONAL_TEAM_FOR_PROXY,
    PERMISSION_DENIED,
    PLATFORM_API_KEY_INVALID,
    PLATFORM_API_KEY_MISSING_GATEWAY_PROXY_SCOPE,
    SYSTEM_CREDENTIAL_ADMIN_REQUIRED,
    SYSTEM_VIRTUAL_KEY_FORBIDDEN,
    VIRTUAL_KEY_DECRYPT_ERROR,
    VIRTUAL_KEY_INVALID,
    VIRTUAL_KEY_NOT_FOUND,
)
from libs.iam.team_http import map_team_access_exception_to_problem

if TYPE_CHECKING:
    from libs.exceptions.base import HttpMappableDomainError

_ProblemBuilder = Callable[[Exception], ProblemContext]


def _entitlement_exhausted_problem(exc: Exception) -> ProblemContext:
    assert isinstance(exc, EntitlementPlanExhaustedError)
    headers: dict[str, str] = {}
    if exc.retry_at:
        headers["X-Plan-Retry-At"] = exc.retry_at
    return ProblemContext(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=str(exc),
        title=default_title_for_status(status.HTTP_429_TOO_MANY_REQUESTS),
        code=GATEWAY_ENTITLEMENT_EXHAUSTED,
        extra={
            "plan_id": exc.plan_id,
            "quota_label": exc.quota_label,
            "reason": exc.reason,
            "retry_at": exc.retry_at,
        },
        headers=headers or None,
    )


def _permission_denied_problem(exc: Exception) -> ProblemContext:
    assert isinstance(exc, PermissionDeniedError)
    return ProblemContext(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=exc.message,
        title=default_title_for_status(status.HTTP_403_FORBIDDEN),
        code=exc.code or PERMISSION_DENIED,
        extra=exc.details or None,
    )


_DOMAIN_PROBLEM_BUILDERS: list[tuple[tuple[type[Exception], ...], _ProblemBuilder]] = [
    ((PermissionDeniedError,), _permission_denied_problem),
    (
        (VirtualKeyInvalidError, PlatformApiKeyInvalidError),
        lambda exc: ProblemContext(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_401_UNAUTHORIZED),
            code=VIRTUAL_KEY_INVALID
            if isinstance(exc, VirtualKeyInvalidError)
            else PLATFORM_API_KEY_INVALID,
            headers={"WWW-Authenticate": "Bearer"},
        ),
    ),
    (
        (PlatformApiKeyMissingGatewayProxyScopeError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_403_FORBIDDEN),
            code=PLATFORM_API_KEY_MISSING_GATEWAY_PROXY_SCOPE,
        ),
    ),
    (
        (NoPersonalTeamForProxyError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_400_BAD_REQUEST),
            code=NO_PERSONAL_TEAM_FOR_PROXY,
        ),
    ),
    (
        (GatewayTeamHeaderInvalidError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_400_BAD_REQUEST),
            code=GATEWAY_TEAM_HEADER_INVALID,
        ),
    ),
    (
        (GatewayTeamHeaderRequiredError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_400_BAD_REQUEST),
            code=GATEWAY_TEAM_HEADER_REQUIRED,
        ),
    ),
    (
        (GatewayVkeyTeamHeaderMismatchError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_400_BAD_REQUEST),
            code=GATEWAY_VKEY_TEAM_HEADER_MISMATCH,
        ),
    ),
    (
        (ApiKeyGatewayGrantDeniedError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_403_FORBIDDEN),
            code=API_KEY_GATEWAY_GRANT_DENIED,
        ),
    ),
    (
        (ApiKeyGatewayGrantRequiredError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_403_FORBIDDEN),
            code=API_KEY_GATEWAY_GRANT_REQUIRED,
        ),
    ),
    (
        (VirtualKeyNotFoundError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_404_NOT_FOUND),
            code=VIRTUAL_KEY_NOT_FOUND,
        ),
    ),
    (
        (SystemVirtualKeyForbiddenError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_403_FORBIDDEN),
            code=SYSTEM_VIRTUAL_KEY_FORBIDDEN,
        ),
    ),
    (
        (CredentialApiKeyDecryptError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_400_BAD_REQUEST),
            code=CREDENTIAL_API_KEY_DECRYPT_ERROR,
        ),
    ),
    (
        (VirtualKeyDecryptError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_400_BAD_REQUEST),
            code=VIRTUAL_KEY_DECRYPT_ERROR,
        ),
    ),
    (
        (CredentialNotFoundError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_404_NOT_FOUND),
            code=CREDENTIAL_NOT_FOUND,
        ),
    ),
    (
        (ManagementEntityNotFoundError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_404_NOT_FOUND),
            code=MANAGEMENT_ENTITY_NOT_FOUND,
        ),
    ),
    (
        (CredentialNameConflictError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_409_CONFLICT),
            code=CREDENTIAL_NAME_CONFLICT,
        ),
    ),
    (
        (InvalidSystemVisibilityError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_400_BAD_REQUEST),
            code=INVALID_SYSTEM_VISIBILITY,
        ),
    ),
    (
        (SystemCredentialAdminRequiredError,),
        lambda exc: ProblemContext(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
            title=default_title_for_status(status.HTTP_403_FORBIDDEN),
            code=SYSTEM_CREDENTIAL_ADMIN_REQUIRED,
        ),
    ),
    ((EntitlementPlanExhaustedError,), _entitlement_exhausted_problem),
]


def problem_context_from_gateway_domain(exc: HttpMappableDomainError) -> ProblemContext:
    """将已知领域异常映射为 ProblemContext；未知 HttpMappable 走 500。"""
    team_ctx = map_team_access_exception_to_problem(exc)
    if team_ctx is not None:
        return team_ctx
    for types, builder in _DOMAIN_PROBLEM_BUILDERS:
        if isinstance(exc, types):
            return builder(exc)
    return ProblemContext(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
        title=default_title_for_status(status.HTTP_500_INTERNAL_SERVER_ERROR),
        code=GATEWAY_DOMAIN_ERROR,
    )


__all__ = ["problem_context_from_gateway_domain"]
