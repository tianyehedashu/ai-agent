"""multi-grant vkey GET /v1/models 集成测试。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.infrastructure.router_singleton import reload_router
from libs.api.paths import openai_compat_base
from tests.integration.gateway.vkey_grant_helpers import (
    create_vkey_with_plain,
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
