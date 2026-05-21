"""凭据 scope 与绑定策略。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.errors import SystemCredentialAdminRequiredError


def assert_system_credential_mutation_allowed(*, is_platform_admin: bool) -> None:
    if not is_platform_admin:
        raise SystemCredentialAdminRequiredError()


def credential_visible_in_tenant(
    *,
    record_tenant_id: uuid.UUID | None,
    request_tenant_id: uuid.UUID,
    is_platform_admin: bool,
) -> bool:
    if is_platform_admin:
        return True
    return record_tenant_id == request_tenant_id


__all__ = [
    "assert_system_credential_mutation_allowed",
    "credential_visible_in_tenant",
]
