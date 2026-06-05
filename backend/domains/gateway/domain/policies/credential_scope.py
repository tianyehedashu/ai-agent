"""凭据 scope 与绑定策略。"""

from __future__ import annotations

from typing import Literal

from domains.gateway.domain.errors import SystemCredentialAdminRequiredError
from domains.gateway.domain.errors import TeamPermissionDeniedError

GatewayModelRegistryTarget = Literal["team", "system"]


def assert_system_credential_mutation_allowed(*, is_platform_admin: bool) -> None:
    if not is_platform_admin:
        raise SystemCredentialAdminRequiredError()


def registry_target_for_credential_scope(scope: str | None) -> GatewayModelRegistryTarget:
    """凭据 API scope → 模型应写入的注册表（team / system）。"""
    if scope == "system":
        return "system"
    return "team"


def is_system_credential_scope(scope: str | None) -> bool:
    return registry_target_for_credential_scope(scope) == "system"


def team_model_credential_scope_allowed(scope: str | None) -> bool:
    """团队 ``gateway_models`` 行是否允许绑定该 scope 的凭据。"""
    return not is_system_credential_scope(scope)


def assert_user_credential_importable(
    credential: object,
    *,
    actor_user_id: "uuid.UUID",
    is_platform_admin: bool,
    tenant_id: "uuid.UUID",
) -> None:
    """Assert the actor may import a user-scope credential to a team.

    Allowed when the actor owns the credential or is a platform admin.
    Raises :class:`TeamPermissionDeniedError` otherwise.
    """
    scope = getattr(credential, "scope", None)
    scope_id = getattr(credential, "scope_id", None)
    if scope != "user":
        from domains.gateway.domain.errors import CredentialNotFoundError

        raise CredentialNotFoundError(str(getattr(credential, "id", "")))
    if scope_id == actor_user_id or is_platform_admin:
        return
    raise TeamPermissionDeniedError(str(tenant_id))


__all__ = [
    "GatewayModelRegistryTarget",
    "assert_system_credential_mutation_allowed",
    "assert_user_credential_importable",
    "is_system_credential_scope",
    "registry_target_for_credential_scope",
    "team_model_credential_scope_allowed",
]
