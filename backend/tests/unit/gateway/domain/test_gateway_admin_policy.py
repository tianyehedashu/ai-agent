"""gateway_admin 策略单元测试。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.errors import SystemCredentialAdminRequiredError
from domains.gateway.domain.policies.gateway_admin import assert_platform_admin


def test_assert_platform_admin_allows() -> None:
    assert_platform_admin(is_platform_admin=True)


def test_assert_platform_admin_denies() -> None:
    with pytest.raises(SystemCredentialAdminRequiredError):
        assert_platform_admin(is_platform_admin=False)
