"""凭据 scope 与绑定策略。"""

from __future__ import annotations

from domains.gateway.domain.errors import SystemCredentialAdminRequiredError


def assert_system_credential_mutation_allowed(*, is_platform_admin: bool) -> None:
    if not is_platform_admin:
        raise SystemCredentialAdminRequiredError()


__all__ = [
    "assert_system_credential_mutation_allowed",
]
