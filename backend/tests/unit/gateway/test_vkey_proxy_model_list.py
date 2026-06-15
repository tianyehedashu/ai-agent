"""vkey_proxy_model_list 编排逻辑单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.application.vkey_proxy_model_list import (
    _ordered_grant_tenant_ids,
    _should_skip_grant_system_row,
)
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel


def _team_model(name: str = "gpt-4o") -> GatewayModel:
    return GatewayModel(
        name=name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=uuid.uuid4(),
        provider="openai",
        tenant_id=uuid.uuid4(),
    )


def _system_model(name: str = "sys-model") -> SystemGatewayModel:
    return SystemGatewayModel(
        name=name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=uuid.uuid4(),
        provider="openai",
    )


def test_ordered_grant_tenant_ids_puts_bound_first() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    vkey = VirtualKeyPrincipal(
        vkey_id=uuid.uuid4(),
        vkey_name="k",
        team_id=bound,
        user_id=uuid.uuid4(),
        allowed_models=(),
        allowed_capabilities=(GatewayCapability.CHAT,),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
        is_system=False,
        granted_team_ids=(grant, bound),
    )
    assert _ordered_grant_tenant_ids(vkey) == (bound, grant)


def test_should_skip_grant_system_row_when_bound_already_lists_bare() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    row = _system_model("shared-sys")
    assert _should_skip_grant_system_row(
        tenant_id=grant,
        bound_team_id=bound,
        row=row,
        bound_system_registry_names={"shared-sys"},
    )


def test_should_not_skip_grant_team_owned_row() -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    row = _team_model("team-only")
    assert not _should_skip_grant_system_row(
        tenant_id=grant,
        bound_team_id=bound,
        row=row,
        bound_system_registry_names={"team-only"},
    )


def test_should_not_skip_bound_team_system_row() -> None:
    bound = uuid.uuid4()
    row = _system_model("sys-a")
    assert not _should_skip_grant_system_row(
        tenant_id=bound,
        bound_team_id=bound,
        row=row,
        bound_system_registry_names=set(),
    )
