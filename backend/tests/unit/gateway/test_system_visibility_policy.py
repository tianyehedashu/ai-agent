"""系统模型可见性：public/restricted、凭据级/模型级 grant、inherit。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.gateway_model_listing import list_merged_models_for_tenant
from domains.gateway.application.management import GatewayManagementReadService
from domains.gateway.application.system_visibility_filter import (
    system_credential_visible_to_subject,
)
from domains.gateway.domain.policies.system_visibility import (
    SystemModelVisibilitySnapshot,
    visible_system_model_ids,
)
from domains.gateway.domain.visibility import Visibility, effective_visibility
from domains.gateway.infrastructure.models.system_gateway import (
    SystemGatewayGrant,
    SystemGatewayModel,
    SystemProviderCredential,
)
from domains.gateway.infrastructure.repositories.system_gateway_grant_repository import (
    SystemGatewayGrantRepository,
)
from domains.tenancy.application.team_service import TeamService


def test_system_credential_visible_to_subject_pure() -> None:
    cid = uuid.uuid4()
    assert system_credential_visible_to_subject(cid, "public", set()) is True
    assert system_credential_visible_to_subject(cid, "restricted", set()) is False
    assert system_credential_visible_to_subject(cid, "restricted", {("credential", cid)}) is True


def test_visible_system_model_ids_pure_policy() -> None:
    mid = uuid.uuid4()
    cid = uuid.uuid4()
    snap = SystemModelVisibilitySnapshot(
        model_id=mid,
        credential_id=cid,
        model_visibility="inherit",
        credential_visibility="restricted",
    )
    granted = {("team", uuid.uuid4())}
    assert mid not in visible_system_model_ids([snap], granted)
    assert mid in visible_system_model_ids([snap], {("credential", cid)})


def test_effective_visibility_inherit_follows_credential() -> None:
    assert effective_visibility("inherit", "restricted") == Visibility.RESTRICTED
    assert effective_visibility("inherit", "public") == Visibility.PUBLIC
    assert effective_visibility("public", "restricted") == Visibility.PUBLIC
    assert effective_visibility("restricted", "public") == Visibility.RESTRICTED


@pytest.mark.asyncio
async def test_restricted_credential_hides_models_without_grant(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="openai",
        name="vis-test-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"vis-model-{uuid.uuid4().hex[:8]}",
        capability="chat",
        real_model="gpt-test",
        credential_id=cred.id,
        provider="openai",
        visibility="inherit",
    )
    db_session.add(model)
    await db_session.flush()

    visible = await list_merged_models_for_tenant(db_session, team.id, user_id=test_user.id)
    assert model.name not in {r.name for r in visible}


@pytest.mark.asyncio
async def test_credential_grant_allows_team(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="openai",
        name="vis-grant-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"vis-grant-{uuid.uuid4().hex[:8]}",
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

    visible = await list_merged_models_for_tenant(db_session, team.id, user_id=test_user.id)
    assert model.name in {r.name for r in visible}


@pytest.mark.asyncio
async def test_model_grant_overrides_restricted_credential_without_credential_grant(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="anthropic",
        name="vis-model-only-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"vis-monly-{uuid.uuid4().hex[:8]}",
        capability="chat",
        real_model="claude-test",
        credential_id=cred.id,
        provider="anthropic",
        visibility="public",
    )
    db_session.add(model)
    await db_session.flush()
    db_session.add(
        SystemGatewayGrant(
            subject_kind="model",
            subject_id=model.id,
            target_kind="team",
            target_id=team.id,
            granted_by=test_user.id,
        )
    )
    await db_session.flush()

    visible = await list_merged_models_for_tenant(db_session, team.id, user_id=test_user.id)
    assert model.name in {r.name for r in visible}


@pytest.mark.asyncio
async def test_user_grant_visible_for_user_target(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    other_user = uuid.uuid4()
    cred = SystemProviderCredential(
        provider="google",
        name="vis-user-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"vis-user-{uuid.uuid4().hex[:8]}",
        capability="chat",
        real_model="gemini-test",
        credential_id=cred.id,
        provider="google",
        visibility="inherit",
    )
    db_session.add(model)
    await db_session.flush()
    db_session.add(
        SystemGatewayGrant(
            subject_kind="credential",
            subject_id=cred.id,
            target_kind="user",
            target_id=test_user.id,
            granted_by=test_user.id,
        )
    )
    await db_session.flush()

    visible_self = await list_merged_models_for_tenant(db_session, team.id, user_id=test_user.id)
    visible_other = await list_merged_models_for_tenant(db_session, team.id, user_id=other_user)
    assert model.name in {r.name for r in visible_self}
    assert model.name not in {r.name for r in visible_other}


@pytest.mark.asyncio
async def test_restricted_model_requires_grant_even_if_credential_public(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="deepseek",
        name="vis-pub-cred",
        api_key_encrypted="enc",
        visibility="public",
    )
    db_session.add(cred)
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"vis-rmodel-{uuid.uuid4().hex[:8]}",
        capability="chat",
        real_model="deepseek-test",
        credential_id=cred.id,
        provider="deepseek",
        visibility="restricted",
    )
    db_session.add(model)
    await db_session.flush()

    visible = await list_merged_models_for_tenant(db_session, team.id, user_id=test_user.id)
    assert model.name not in {r.name for r in visible}

    db_session.add(
        SystemGatewayGrant(
            subject_kind="model",
            subject_id=model.id,
            target_kind="team",
            target_id=team.id,
            granted_by=test_user.id,
        )
    )
    await db_session.flush()
    visible2 = await list_merged_models_for_tenant(db_session, team.id, user_id=test_user.id)
    assert model.name in {r.name for r in visible2}


@pytest.mark.asyncio
async def test_registry_scope_system_skips_visibility_filter(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = SystemProviderCredential(
        provider="zhipu",
        name="vis-admin-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(cred)
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"vis-admin-{uuid.uuid4().hex[:8]}",
        capability="chat",
        real_model="glm-test",
        credential_id=cred.id,
        provider="zhipu",
        visibility="inherit",
    )
    db_session.add(model)
    await db_session.flush()

    reads = GatewayManagementReadService(db_session)
    admin_rows = await reads.list_gateway_models(
        team.id, registry_scope="system", only_enabled=False
    )
    assert model.name in {r.name for r in admin_rows}
    callable_rows = await reads.list_gateway_models(
        team.id,
        registry_scope="callable",
        only_enabled=False,
        user_id=test_user.id,
    )
    assert model.name not in {r.name for r in callable_rows}


@pytest.mark.asyncio
async def test_credential_summaries_hide_restricted_system_without_grant(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    public_cred = SystemProviderCredential(
        provider="openai",
        name="summary-public-cred",
        api_key_encrypted="enc",
        visibility="public",
    )
    restricted_cred = SystemProviderCredential(
        provider="anthropic",
        name="summary-restricted-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add_all([public_cred, restricted_cred])
    await db_session.flush()

    reads = GatewayManagementReadService(db_session)
    summaries = await reads.list_credential_summaries_for_team(
        team.id,
        user_id=test_user.id,
        is_platform_admin=False,
    )
    ids = {row.id for row in summaries}
    assert public_cred.id in ids
    assert restricted_cred.id not in ids


@pytest.mark.asyncio
async def test_credential_summaries_include_restricted_system_with_grant(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    restricted_cred = SystemProviderCredential(
        provider="anthropic",
        name="summary-granted-cred",
        api_key_encrypted="enc",
        visibility="restricted",
    )
    db_session.add(restricted_cred)
    await db_session.flush()
    db_session.add(
        SystemGatewayGrant(
            subject_kind="credential",
            subject_id=restricted_cred.id,
            target_kind="team",
            target_id=team.id,
            granted_by=test_user.id,
        )
    )
    await db_session.flush()

    reads = GatewayManagementReadService(db_session)
    summaries = await reads.list_credential_summaries_for_team(
        team.id,
        user_id=test_user.id,
        is_platform_admin=False,
    )
    assert restricted_cred.id in {row.id for row in summaries}


@pytest.mark.asyncio
async def test_grant_repository_idempotent_create(db_session, test_user) -> None:
    subject_id = uuid.uuid4()
    target_id = uuid.uuid4()
    repo = SystemGatewayGrantRepository(db_session)
    first = await repo.create(
        subject_kind="model",
        subject_id=subject_id,
        target_kind="team",
        target_id=target_id,
        granted_by=test_user.id,
    )
    second = await repo.create(
        subject_kind="model",
        subject_id=subject_id,
        target_kind="team",
        target_id=target_id,
        granted_by=test_user.id,
    )
    assert first.id == second.id
