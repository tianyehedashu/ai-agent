"""个人资源 grant：解析、凭据绑定、Router 编码单测。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.catalog.gateway_model_listing import (
    list_merged_models_for_tenant,
    resolve_by_name_visible,
)
from domains.gateway.application.catalog.model_or_route_resolution import resolve_model_or_route
from domains.gateway.application.grant.credential_binding import (
    resolve_bindable_credential,
)
from domains.gateway.application.grant.management.resource_grant_writes import (
    ResourceGrantWriteService,
)
from domains.gateway.application.grant.resource_grant_resolution import (
    resolve_granted_model_by_name,
)
from domains.gateway.application.route.router_model_name import router_model_name_for_client
from domains.gateway.domain.errors import VkeyAmbiguousModelError
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


async def _seed_personal_byok(
    db_session,
    test_user,
    *,
    model_name: str,
    provider: str = "openai",
) -> tuple[object, object, object]:
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="user",
        scope_id=test_user.id,
        provider=provider,
        name=f"byok-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    model = await GatewayModelRepository(db_session).create(
        tenant_id=personal.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider=provider,
    )
    await db_session.flush()
    return personal, cred, model


@pytest.mark.asyncio
async def test_granted_model_resolves_on_shared_team(db_session, test_user) -> None:
    teams = TeamService(db_session)
    personal, _, model = await _seed_personal_byok(
        db_session, test_user, model_name=f"gr-res-{uuid.uuid4().hex[:6]}"
    )
    shared = await teams.create_team(
        name=f"shared-gr-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    await ResourceGrantWriteService(db_session).grant_model_to_teams(
        model_id=model.id,
        target_team_ids=[shared.id],
        actor_user_id=test_user.id,
    )
    await db_session.flush()

    row = await resolve_by_name_visible(db_session, shared.id, model.name)
    assert row is not None
    assert row.id == model.id
    assert row.tenant_id == personal.id


@pytest.mark.asyncio
async def test_granted_model_slug_prefix_resolves_owner_row(db_session, test_user) -> None:
    teams = TeamService(db_session)
    personal, _, model = await _seed_personal_byok(
        db_session, test_user, model_name=f"slug-gr-{uuid.uuid4().hex[:6]}"
    )
    shared = await teams.create_team(
        name=f"shared-slug-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    await ResourceGrantWriteService(db_session).grant_model_to_teams(
        model_id=model.id,
        target_team_ids=[shared.id],
        actor_user_id=test_user.id,
    )
    await db_session.flush()

    prefixed = f"{personal.slug}/{model.name}"
    row = await resolve_granted_model_by_name(db_session, shared.id, prefixed)
    assert row is not None
    assert row.id == model.id


@pytest.mark.asyncio
async def test_granted_model_bare_name_ambiguous_raises(db_session, test_user) -> None:
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-amb-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    other = User(
        email=f"other-gr-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hashed",
        name="Other",
    )
    db_session.add(other)
    await db_session.flush()
    other_personal = await teams.ensure_personal_team(other.id)
    await teams.add_member(shared.id, other.id, "member")

    dup_name = f"dup-gr-{uuid.uuid4().hex[:6]}"
    for owner_id, uid, actor_id in (
        (test_user.id, personal.id, test_user.id),
        (other.id, other_personal.id, other.id),
    ):
        cred = await ProviderCredentialRepository(db_session).create(
            scope="user",
            scope_id=owner_id,
            provider="openai",
            name=f"c-{uuid.uuid4().hex[:4]}",
            api_key_encrypted=encrypt_value(
                "sk-fake",
                derive_encryption_key(settings.secret_key.get_secret_value()),
            ),
            api_base=None,
        )
        model = await GatewayModelRepository(db_session).create(
            tenant_id=uid,
            name=dup_name,
            capability="chat",
            real_model="gpt-4o-mini",
            credential_id=cred.id,
            provider="openai",
        )
        await ResourceGrantWriteService(db_session).grant_model_to_teams(
            model_id=model.id,
            target_team_ids=[shared.id],
            actor_user_id=actor_id,
        )
    await db_session.flush()

    with pytest.raises(VkeyAmbiguousModelError):
        await resolve_granted_model_by_name(db_session, shared.id, dup_name)


@pytest.mark.asyncio
async def test_get_bindable_accepts_granted_byok_credential(db_session, test_user) -> None:
    teams = TeamService(db_session)
    personal, cred, model = await _seed_personal_byok(
        db_session, test_user, model_name=f"bind-gr-{uuid.uuid4().hex[:6]}"
    )
    shared = await teams.create_team(
        name=f"shared-bind-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    await ResourceGrantWriteService(db_session).grant_credential_to_teams(
        credential_id=cred.id,
        target_team_ids=[shared.id],
        actor_user_id=test_user.id,
    )
    await db_session.flush()

    bound = await resolve_bindable_credential(
        db_session,
        credential_id=cred.id,
        tenant_id=shared.id,
        is_platform_admin=False,
    )
    assert bound is not None
    assert bound.id == cred.id
    _ = model


@pytest.mark.asyncio
async def test_router_model_name_uses_owner_personal_team(db_session, test_user) -> None:
    teams = TeamService(db_session)
    personal, _, model = await _seed_personal_byok(
        db_session, test_user, model_name=f"enc-gr-{uuid.uuid4().hex[:6]}"
    )
    shared = await teams.create_team(
        name=f"shared-enc-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    await ResourceGrantWriteService(db_session).grant_model_to_teams(
        model_id=model.id,
        target_team_ids=[shared.id],
        actor_user_id=test_user.id,
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(
        db_session,
        shared.id,
        model.name,
        user_id=None,
        enable_personal_fallback=False,
    )
    assert resolved is not None
    encoded = router_model_name_for_client(shared.id, model.name, resolved)
    assert encoded == f"gw/t/{personal.id}/{model.name}"


@pytest.mark.asyncio
async def test_list_merged_includes_granted_model(db_session, test_user) -> None:
    teams = TeamService(db_session)
    _, _, model = await _seed_personal_byok(
        db_session, test_user, model_name=f"merge-gr-{uuid.uuid4().hex[:6]}"
    )
    shared = await teams.create_team(
        name=f"shared-merge-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    await ResourceGrantWriteService(db_session).grant_model_to_teams(
        model_id=model.id,
        target_team_ids=[shared.id],
        actor_user_id=test_user.id,
    )
    await db_session.flush()

    merged = await list_merged_models_for_tenant(db_session, shared.id)
    names = [m.name for m in merged]
    assert model.name in names


def test_granted_record_encodes_owner_tenant_not_caller() -> None:
    owner_team = uuid.uuid4()
    caller_team = uuid.uuid4()
    record = SimpleNamespace(name="shared-alias", tenant_id=owner_team)
    resolved = SimpleNamespace(
        record=record,
        route=None,
        via_route=None,
        delegated_grant_team_id=None,
        exposed_alias=None,
    )
    encoded = router_model_name_for_client(caller_team, "shared-alias", resolved)
    assert encoded == f"gw/t/{owner_team}/shared-alias"
