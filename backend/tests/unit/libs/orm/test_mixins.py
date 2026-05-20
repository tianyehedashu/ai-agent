"""ORM Mixin 协议与 Gateway 模型 tenant_id 暴露。"""

from __future__ import annotations

from libs.orm.base import PolicyTargetMixin, TenantScopedMixin


def test_gateway_model_tenant_id_column() -> None:
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel

    assert issubclass(GatewayModel, TenantScopedMixin)
    assert "tenant_id" in GatewayModel.__table__.c
    assert "team_id" not in GatewayModel.__table__.c


def test_entitlement_plan_policy_target() -> None:
    from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan

    assert issubclass(EntitlementPlan, PolicyTargetMixin)
    assert "target_kind" in EntitlementPlan.__table__.c
    assert "target_id" in EntitlementPlan.__table__.c
    assert "scope" not in EntitlementPlan.__table__.c
    assert "scope_id" not in EntitlementPlan.__table__.c
