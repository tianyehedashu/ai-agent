"""IAM / 租户抽象与网关适配的契约单测。"""

from __future__ import annotations

from unittest.mock import MagicMock
import uuid

import pytest

from domains.gateway.infrastructure.iam.default_tenant_provisioner import (
    GatewayDefaultTenantProvisioner,
)
from domains.identity.infrastructure.default_tenant_lifecycle import (
    provision_default_tenant_for_new_user,
)
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from libs.iam.external_idp import (
    external_idp_configured,
    parse_external_idp_claims,
)
from libs.iam.tenancy import TenantId


class _FailingProvisioner:
    async def ensure_default_tenant(self, session, user_id, *, display_name=None):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_provision_default_tenant_logs_on_failure() -> None:
    session = MagicMock()
    ok = await provision_default_tenant_for_new_user(
        session=session,
        provisioner=_FailingProvisioner(),
        user_id=uuid.uuid4(),
        display_name="x",
        log=MagicMock(),
    )
    assert ok is False


@pytest.mark.asyncio
async def test_gateway_default_tenant_provisioner_returns_tenant_id(db_session, test_user):
    prov = GatewayDefaultTenantProvisioner()
    tid = await prov.ensure_default_tenant(
        db_session,
        test_user.id,
        display_name="u",
    )
    assert isinstance(tid, uuid.UUID)


@pytest.mark.asyncio
async def test_tenancy_membership_adapter_owner(db_session, test_user):
    from domains.tenancy.application.team_service import TeamService

    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    adapter = TenancyMembershipAdapter()
    role = await adapter.member_role(
        db_session,
        tenant_id=TenantId(team.id),
        user_id=test_user.id,
    )
    assert role == "owner"


def test_parse_external_idp_claims_tenant_and_org() -> None:
    uid = str(uuid.uuid4())
    v = parse_external_idp_claims({"sub": "abc", "tenant_id": uid})
    assert v.subject == "abc"
    assert v.tenant_id == uuid.UUID(uid)

    v2 = parse_external_idp_claims({"sub": "x", "org_id": uid})
    assert v2.tenant_id == uuid.UUID(uid)


def test_external_idp_configured_reads_settings() -> None:
    from types import SimpleNamespace

    assert external_idp_configured(
        SimpleNamespace(federation_mode="oidc", oidc_issuer_url="https://issuer.example")
    )
    assert external_idp_configured(
        SimpleNamespace(
            federation_mode="oauth2_introspection",
            oauth2_introspection_url="https://intro",
            oidc_issuer_url=None,
        )
    )
    assert not external_idp_configured(
        SimpleNamespace(federation_mode="none", oidc_issuer_url=None, oauth2_introspection_url=None)
    )
    assert external_idp_configured(
        SimpleNamespace(federation_mode="none", oidc_issuer_url="https://legacy-only")
    )
