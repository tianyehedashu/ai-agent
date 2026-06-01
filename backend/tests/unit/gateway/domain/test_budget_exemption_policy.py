"""平台配额豁免策略单测（纯函数，个人工作区模型判定）。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

from domains.gateway.domain.policies.budget_exemption_policy import (
    is_personal_team_gateway_model,
    should_skip_platform_budget_preflight,
)


def test_is_personal_team_model_true_when_tenant_matches() -> None:
    personal = uuid.uuid4()
    assert is_personal_team_gateway_model(
        SimpleNamespace(tenant_id=personal), personal_team_id=personal
    )


def test_is_personal_team_model_false_for_other_team() -> None:
    assert not is_personal_team_gateway_model(
        SimpleNamespace(tenant_id=uuid.uuid4()), personal_team_id=uuid.uuid4()
    )


def test_is_personal_team_model_false_without_personal_team() -> None:
    assert not is_personal_team_gateway_model(
        SimpleNamespace(tenant_id=uuid.uuid4()), personal_team_id=None
    )


def test_is_personal_team_model_false_for_system_model() -> None:
    # 系统模型无 tenant_id，始终受平台配额约束。
    assert not is_personal_team_gateway_model(
        SimpleNamespace(tenant_id=None), personal_team_id=uuid.uuid4()
    )


def test_skip_returns_false_when_unresolved() -> None:
    assert not should_skip_platform_budget_preflight(
        None, billing_team_id=uuid.uuid4(), personal_team_id=uuid.uuid4()
    )


def test_skip_true_when_billing_team_is_personal_team() -> None:
    personal = uuid.uuid4()
    assert should_skip_platform_budget_preflight(
        personal, billing_team_id=personal, personal_team_id=personal
    )


def test_skip_true_for_cross_team_personal_model_without_extra_query() -> None:
    # 共享 vkey 调个人别名：tenant 非计费团队即可判定豁免，无需 personal_team_id。
    other_tenant = uuid.uuid4()
    assert should_skip_platform_budget_preflight(
        other_tenant, billing_team_id=uuid.uuid4(), personal_team_id=None
    )


def test_skip_false_for_shared_team_model() -> None:
    billing = uuid.uuid4()
    assert not should_skip_platform_budget_preflight(
        billing, billing_team_id=billing, personal_team_id=uuid.uuid4()
    )


def test_skip_false_for_system_model() -> None:
    assert not should_skip_platform_budget_preflight(
        None, billing_team_id=uuid.uuid4(), personal_team_id=uuid.uuid4()
    )
