"""platform_budget_display 领域规则单测。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.budget.platform_budget_display import (
    PlatformBudgetLogScope,
    platform_log_fallback_supported,
)


def test_system_budget_disables_log_fallback() -> None:
    scope = PlatformBudgetLogScope(
        target_kind="system",
        target_id=None,
        model_name=None,
        credential_id=None,
        tenant_id=None,
    )
    assert platform_log_fallback_supported(scope) is False


def test_user_budget_enables_log_fallback_with_tenant() -> None:
    scope = PlatformBudgetLogScope(
        target_kind="user",
        target_id=uuid.uuid4(),
        model_name=None,
        credential_id=None,
        tenant_id=uuid.uuid4(),
    )
    assert platform_log_fallback_supported(scope) is True
