"""tenant_scoped_orm_dict / apply_tenant_team_mirror 单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.presentation.tenant_scoped_response import (
    apply_tenant_team_mirror,
    tenant_scoped_orm_dict,
)


def test_tenant_scoped_orm_dict_mirrors_team_id() -> None:
    tenant = uuid.uuid4()
    row = GatewayModel(
        tenant_id=tenant,
        name="alias",
        capability="chat",
        real_model="gpt-4",
        credential_id=uuid.uuid4(),
        provider="openai",
    )
    data = tenant_scoped_orm_dict(row)
    assert data["tenant_id"] == tenant
    assert data["team_id"] == tenant


def test_apply_tenant_team_mirror_from_tenant_id() -> None:
    tenant = uuid.uuid4()
    out = apply_tenant_team_mirror({"tenant_id": tenant})
    assert out["team_id"] == tenant


def test_apply_tenant_team_mirror_from_team_id() -> None:
    tenant = uuid.uuid4()
    out = apply_tenant_team_mirror({"team_id": tenant})
    assert out["tenant_id"] == tenant
