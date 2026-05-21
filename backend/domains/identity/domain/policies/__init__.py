"""Identity domain policies."""

from domains.identity.domain.policies.platform_role_policy import (
    assert_bootstrap_grant_admin,
    assert_bootstrap_revoke_admin,
    assert_can_change_platform_role,
    is_assignable_platform_role,
)

__all__ = [
    "assert_bootstrap_grant_admin",
    "assert_bootstrap_revoke_admin",
    "assert_can_change_platform_role",
    "is_assignable_platform_role",
]
