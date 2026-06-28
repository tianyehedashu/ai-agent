"""Gateway 管理面：平台 admin 与系统级资源策略。"""

from __future__ import annotations

from domains.gateway.domain.errors import SystemCredentialAdminRequiredError


def assert_platform_admin(*, is_platform_admin: bool) -> None:
    if not is_platform_admin:
        raise SystemCredentialAdminRequiredError()


__all__ = ["assert_platform_admin"]
