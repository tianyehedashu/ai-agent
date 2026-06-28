"""gateway_model_listing：合并列表、按名解析、callable 系统模型名。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.catalog.gateway_model_listing import (
    list_callable_system_model_names,
    list_merged_models_for_tenant,
    resolve_by_name_visible,
)
from domains.gateway.application.management import GatewayManagementReadService
from domains.gateway.domain.catalog.model_selection import registry_kind_for_merged_row
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import (
    SystemGatewayGrant,
    SystemGatewayModel,
    SystemProviderCredential,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


@pytest.mark.asyncio
async def test_list_callable_system_model_names_excludes_restricted_without_grant(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="openai",
        name="callable-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model_name = f"callable-hidden-{uuid.uuid4().hex[:8]}"
    db_session.add(
        SystemGatewayModel(
            name=model_name,
            capability="chat",
            real_model="gpt-hidden",
            credential_id=cred.id,
            provider="openai",
            visibility="inherit",
        )
    )
    await db_session.flush()

    names = await list_callable_system_model_names(db_session, team.id, user_id=test_user.id)
    assert model_name not in names


@pytest.mark.asyncio
async def test_list_callable_system_model_names_includes_after_team_grant(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="openai",
        name="callable-grant-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model_name = f"callable-grant-{uuid.uuid4().hex[:8]}"
    model = SystemGatewayModel(
        name=model_name,
        capability="chat",
        real_model="gpt-grant",
        credential_id=cred.id,
        provider="openai",
        visibility="inherit",
    )
    db_session.add(model)
    await db_session.flush()
    db_session.add(
        SystemGatewayGrant(
            subject_kind="credential",
            subject_id=cred.id,
            target_kind="team",
            target_id=team.id,
            granted_by=test_user.id,
        )
    )
    await db_session.flush()

    names = await list_callable_system_model_names(db_session, team.id, user_id=test_user.id)
    assert model_name in names

    reads = GatewayManagementReadService(db_session)
    via_reads = await reads.list_callable_system_model_names(team.id, user_id=test_user.id)
    assert model_name in via_reads


@pytest.mark.asyncio
async def test_list_merged_apply_visibility_filter_false_includes_restricted(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="mistral",
        name="no-filter-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model_name = f"no-filter-{uuid.uuid4().hex[:8]}"
    db_session.add(
        SystemGatewayModel(
            name=model_name,
            capability="chat",
            real_model="mistral-test",
            credential_id=cred.id,
            provider="mistral",
            visibility="inherit",
        )
    )
    await db_session.flush()

    filtered = await list_merged_models_for_tenant(
        db_session, team.id, user_id=test_user.id, apply_visibility_filter=True
    )
    unfiltered = await list_merged_models_for_tenant(
        db_session,
        team.id,
        user_id=test_user.id,
        apply_visibility_filter=False,
    )
    assert model_name not in {r.name for r in filtered}
    assert model_name in {r.name for r in unfiltered}


@pytest.mark.asyncio
async def test_resolve_by_name_visible_team_row_without_grant(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team.id, name="team-resolve-cred")
    model_name = f"team-only-{uuid.uuid4().hex[:8]}"
    db_session.add(
        GatewayModel(
            tenant_id=team.id,
            name=model_name,
            capability="chat",
            real_model="gpt-team",
            credential_id=cred.id,
            provider="openai",
        )
    )
    await db_session.flush()

    resolved = await resolve_by_name_visible(db_session, team.id, model_name, user_id=test_user.id)
    assert resolved is not None
    assert registry_kind_for_merged_row(resolved) == "team"


@pytest.mark.asyncio
async def test_resolve_by_name_visible_restricted_system_none_without_grant(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="cohere",
        name="resolve-hidden-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model_name = f"resolve-hidden-{uuid.uuid4().hex[:8]}"
    db_session.add(
        SystemGatewayModel(
            name=model_name,
            capability="chat",
            real_model="cohere-test",
            credential_id=cred.id,
            provider="cohere",
            visibility="inherit",
        )
    )
    await db_session.flush()

    resolved = await resolve_by_name_visible(db_session, team.id, model_name, user_id=test_user.id)
    assert resolved is None


@pytest.mark.asyncio
async def test_resolve_by_name_visible_restricted_system_with_grant(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="cohere",
        name="resolve-grant-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model_name = f"resolve-grant-{uuid.uuid4().hex[:8]}"
    model = SystemGatewayModel(
        name=model_name,
        capability="chat",
        real_model="cohere-grant",
        credential_id=cred.id,
        provider="cohere",
        visibility="inherit",
    )
    db_session.add(model)
    await db_session.flush()
    db_session.add(
        SystemGatewayGrant(
            subject_kind="credential",
            subject_id=cred.id,
            target_kind="team",
            target_id=team.id,
            granted_by=test_user.id,
        )
    )
    await db_session.flush()

    resolved = await resolve_by_name_visible(db_session, team.id, model_name, user_id=test_user.id)
    assert resolved is not None
    assert resolved.name == model_name
    assert registry_kind_for_merged_row(resolved) == "system"


@pytest.mark.asyncio
async def test_resolve_by_name_visible_prefers_tenant_over_restricted_system(
    db_session, test_user
) -> None:
    """同名时租户行优先，不因 system 受限而返回 None。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    tenant_cred = await create_tenant_test_credential(
        db_session, team.id, name="shadow-tenant-cred"
    )
    sys_cred = SystemProviderCredential(
        provider="openai",
        name="shadow-sys-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(sys_cred)
    await db_session.flush()
    shared_name = f"shadow-{uuid.uuid4().hex[:8]}"
    db_session.add(
        GatewayModel(
            tenant_id=team.id,
            name=shared_name,
            capability="chat",
            real_model="gpt-shadow-team",
            credential_id=tenant_cred.id,
            provider="openai",
        )
    )
    db_session.add(
        SystemGatewayModel(
            name=shared_name,
            capability="chat",
            real_model="gpt-shadow-sys",
            credential_id=sys_cred.id,
            provider="openai",
            visibility="inherit",
        )
    )
    await db_session.flush()

    resolved = await resolve_by_name_visible(db_session, team.id, shared_name, user_id=test_user.id)
    assert resolved is not None
    assert registry_kind_for_merged_row(resolved) == "team"
    repo = GatewayModelRepository(db_session)
    assert await repo.get_by_name(team.id, shared_name) is not None


@pytest.mark.asyncio
async def test_resolve_by_name_visible_skips_disabled_tenant_for_system(
    db_session, test_user
) -> None:
    """disabled 租户行不遮蔽同名可见 system 行（与 Router 仅注册 enabled 一致）。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    tenant_cred = await create_tenant_test_credential(
        db_session, team.id, name="disabled-shadow-cred"
    )
    sys_cred = SystemProviderCredential(
        provider="openai",
        name="disabled-shadow-sys-cred",
        api_key_encrypted="enc",
        visibility="public",
    )
    db_session.add(sys_cred)
    await db_session.flush()
    shared_name = f"disabled-shadow-{uuid.uuid4().hex[:8]}"
    db_session.add(
        GatewayModel(
            tenant_id=team.id,
            name=shared_name,
            capability="chat",
            real_model="gpt-disabled-team",
            credential_id=tenant_cred.id,
            provider="openai",
            enabled=False,
        )
    )
    db_session.add(
        SystemGatewayModel(
            name=shared_name,
            capability="chat",
            real_model="gpt-disabled-sys",
            credential_id=sys_cred.id,
            provider="openai",
            visibility="inherit",
        )
    )
    await db_session.flush()

    resolved = await resolve_by_name_visible(db_session, team.id, shared_name, user_id=test_user.id)
    assert resolved is not None
    assert registry_kind_for_merged_row(resolved) == "system"
    assert resolved.real_model == "gpt-disabled-sys"


@pytest.mark.asyncio
async def test_resolve_by_name_visible_disabled_tenant_without_system_is_none(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team.id, name="disabled-only-cred")
    model_name = f"disabled-only-{uuid.uuid4().hex[:8]}"
    db_session.add(
        GatewayModel(
            tenant_id=team.id,
            name=model_name,
            capability="chat",
            real_model="gpt-disabled",
            credential_id=cred.id,
            provider="openai",
            enabled=False,
        )
    )
    await db_session.flush()

    resolved = await resolve_by_name_visible(db_session, team.id, model_name, user_id=test_user.id)
    assert resolved is None
