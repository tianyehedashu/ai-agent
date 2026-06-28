"""multi-grant vkey GET /v1/models 集成测试。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.infrastructure.litellm.router_singleton import reload_router
from libs.api.paths import openai_compat_base
from tests.integration.gateway.vkey_grant_helpers import (
    create_vkey_with_plain,
    ensure_homonym_slug_grant_teams,
    ensure_two_teams,
    setup_team_model,
    setup_team_route,
)

_OPENAI_MODELS = f"{openai_compat_base()}/models"


def _model_ids(payload: dict[str, object]) -> set[str]:
    data = payload.get("data")
    assert isinstance(data, list)
    ids: set[str] = set()
    for item in data:
        assert isinstance(item, dict)
        model_id = item.get("id")
        assert isinstance(model_id, str)
        ids.add(model_id)
    return ids


@pytest.mark.integration
class TestVkeyGrantsModelsList:
    @pytest.mark.asyncio
    async def test_homonym_model_lists_bare_and_prefixed(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        shared_slug = shared.slug
        model_name = f"homonym-{uuid.uuid4().hex[:6]}"
        await setup_team_model(
            dev_client, primary.id, auth_headers, model_name=model_name
        )
        await setup_team_model(
            dev_client, shared.id, auth_headers, model_name=model_name
        )
        vkey_id, plain_key = await create_vkey_with_plain(
            dev_client, primary.id, auth_headers
        )
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        r = await dev_client.get(
            _OPENAI_MODELS,
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r.status_code == 200, r.text
        ids = _model_ids(r.json())
        assert model_name in ids
        assert f"{shared_slug}/{model_name}" in ids

    @pytest.mark.asyncio
    async def test_grant_only_model_appears_with_slug_prefix(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        shared_slug = shared.slug
        grant_only = f"grant-only-{uuid.uuid4().hex[:6]}"
        await setup_team_model(
            dev_client, shared.id, auth_headers, model_name=grant_only
        )
        vkey_id, plain_key = await create_vkey_with_plain(
            dev_client, primary.id, auth_headers
        )
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        r = await dev_client.get(
            _OPENAI_MODELS,
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r.status_code == 200, r.text
        ids = _model_ids(r.json())
        assert f"{shared_slug}/{grant_only}" in ids
        assert grant_only not in ids

    @pytest.mark.asyncio
    async def test_allowed_models_filters_grant_entries(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        shared_slug = shared.slug
        allowed_name = f"allowed-{uuid.uuid4().hex[:6]}"
        blocked_name = f"blocked-{uuid.uuid4().hex[:6]}"
        await setup_team_model(
            dev_client, shared.id, auth_headers, model_name=allowed_name
        )
        await setup_team_model(
            dev_client, shared.id, auth_headers, model_name=blocked_name
        )
        r_key = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys",
            headers=auth_headers,
            json={
                "name": f"mvkey-{uuid.uuid4().hex[:8]}",
                "allowed_models": [allowed_name],
            },
        )
        assert r_key.status_code == 201, r_key.text
        vkey_id = r_key.json()["id"]
        plain_key = r_key.json()["plain_key"]
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        r = await dev_client.get(
            _OPENAI_MODELS,
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r.status_code == 200, r.text
        ids = _model_ids(r.json())
        assert f"{shared_slug}/{allowed_name}" in ids
        assert f"{shared_slug}/{blocked_name}" not in ids

    @pytest.mark.asyncio
    async def test_single_grant_vkey_unchanged_bare_ids(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        primary, _shared = await ensure_two_teams(db_session, test_user)
        model_name = f"solo-{uuid.uuid4().hex[:6]}"
        await setup_team_model(
            dev_client, primary.id, auth_headers, model_name=model_name
        )
        _vkey_id, plain_key = await create_vkey_with_plain(
            dev_client, primary.id, auth_headers
        )
        await reload_router(db_session)

        r = await dev_client.get(
            _OPENAI_MODELS,
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r.status_code == 200, r.text
        ids = _model_ids(r.json())
        assert model_name in ids
        assert not any(
            model_id != model_name and model_id.endswith(f"/{model_name}")
            for model_id in ids
        )

    @pytest.mark.asyncio
    async def test_grant_team_route_appears_with_slug_prefix(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        shared_slug = shared.slug
        model_name = f"route-base-{uuid.uuid4().hex[:6]}"
        virtual_model = f"route-vm-{uuid.uuid4().hex[:6]}"
        await setup_team_model(
            dev_client, shared.id, auth_headers, model_name=model_name
        )
        await setup_team_route(
            dev_client,
            shared.id,
            auth_headers,
            virtual_model=virtual_model,
            primary_model=model_name,
        )
        vkey_id, plain_key = await create_vkey_with_plain(
            dev_client, primary.id, auth_headers
        )
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        r = await dev_client.get(
            _OPENAI_MODELS,
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r.status_code == 200, r.text
        ids = _model_ids(r.json())
        assert f"{shared_slug}/{virtual_model}" in ids
        assert virtual_model not in ids

    @pytest.mark.asyncio
    async def test_multi_grant_exposes_shared_route_with_slug_prefix(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        """委派共享进 grant team 的个人路由，对 multi-grant vkey 以 slug 前缀暴露。"""
        primary, shared = await ensure_two_teams(db_session, test_user)
        shared_slug = shared.slug
        model_name = f"sm-{uuid.uuid4().hex[:6]}"
        await setup_team_model(
            dev_client, primary.id, auth_headers, model_name=model_name
        )
        r_route = await dev_client.post(
            "/api/v1/gateway/my-routes",
            headers=auth_headers,
            json={
                "virtual_model": f"vm-{uuid.uuid4().hex[:6]}",
                "primary_models": [model_name],
            },
        )
        assert r_route.status_code == 201, r_route.text
        route_id = r_route.json()["id"]
        alias = f"shared-{uuid.uuid4().hex[:6]}"
        r_grant_route = await dev_client.post(
            f"/api/v1/gateway/my-routes/{route_id}/grants",
            headers=auth_headers,
            json={"target_tenant_id": str(shared.id), "exposed_alias": alias},
        )
        assert r_grant_route.status_code == 201, r_grant_route.text

        vkey_id, plain_key = await create_vkey_with_plain(
            dev_client, primary.id, auth_headers
        )
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        r = await dev_client.get(
            _OPENAI_MODELS,
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r.status_code == 200, r.text
        ids = _model_ids(r.json())
        assert f"{shared_slug}/{alias}" in ids

    @pytest.mark.asyncio
    async def test_homonym_slug_omits_grant_team_models_from_list(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        """grants 内 homonym slug 的 team：列表与 dispatch 均不可用 prefix，grant 模型不出现在列表。"""
        primary, grant_a, grant_b, dup_slug = await ensure_homonym_slug_grant_teams(
            db_session, test_user
        )
        bound_model = f"bound-{uuid.uuid4().hex[:6]}"
        grant_a_model = f"grant-a-{uuid.uuid4().hex[:6]}"
        grant_b_model = f"grant-b-{uuid.uuid4().hex[:6]}"
        await setup_team_model(
            dev_client, primary.id, auth_headers, model_name=bound_model
        )
        await setup_team_model(
            dev_client, grant_a.id, auth_headers, model_name=grant_a_model
        )
        await setup_team_model(
            dev_client, grant_b.id, auth_headers, model_name=grant_b_model
        )
        vkey_id, plain_key = await create_vkey_with_plain(
            dev_client, primary.id, auth_headers
        )
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(grant_a.id), str(grant_b.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        r = await dev_client.get(
            _OPENAI_MODELS,
            headers={"Authorization": f"Bearer {plain_key}"},
        )
        assert r.status_code == 200, r.text
        ids = _model_ids(r.json())
        assert bound_model in ids
        assert f"{dup_slug}/{grant_a_model}" not in ids
        assert f"{dup_slug}/{grant_b_model}" not in ids
        assert grant_a_model not in ids
        assert grant_b_model not in ids

    @pytest.mark.asyncio
    async def test_create_vkey_with_granted_team_ids(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        vkey_id, _plain = await create_vkey_with_plain(
            dev_client,
            primary.id,
            auth_headers,
            granted_team_ids=[shared.id],
        )
        r_grants = await dev_client.get(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
        )
        assert r_grants.status_code == 200, r_grants.text
        grants = r_grants.json()
        tenant_ids = {g["tenant_id"] for g in grants}
        assert str(primary.id) in tenant_ids
        assert str(shared.id) in tenant_ids
        r_create = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys",
            headers=auth_headers,
            json={
                "name": f"mvkey-check-{uuid.uuid4().hex[:6]}",
                "granted_team_ids": [str(shared.id), str(primary.id)],
            },
        )
        assert r_create.status_code == 201, r_create.text
        created = r_create.json()
        assert str(primary.id) in created["granted_team_ids"]
        assert str(shared.id) in created["granted_team_ids"]

    @pytest.mark.asyncio
    async def test_create_vkey_rejects_grant_to_non_member_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        from domains.identity.infrastructure.models.user import User
        from domains.tenancy.application.team_service import TeamService

        primary, _shared = await ensure_two_teams(db_session, test_user)
        other = User(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed_password",
            name="Other",
        )
        db_session.add(other)
        await db_session.flush()
        foreign_team = await TeamService(db_session).create_team(
            name=f"foreign-{uuid.uuid4().hex[:4]}",
            owner_user_id=other.id,
        )
        await db_session.commit()

        r = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys",
            headers=auth_headers,
            json={
                "name": f"mvkey-bad-{uuid.uuid4().hex[:6]}",
                "granted_team_ids": [str(foreign_team.id)],
            },
        )
        assert r.status_code == 422, r.text
