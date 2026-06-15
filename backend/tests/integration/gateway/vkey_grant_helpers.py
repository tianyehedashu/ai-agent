"""跨团队 vkey 集成测试共享 helpers。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.management.virtual_key_team_grant_writes import (
    ensure_self_grant_for_vkey,
)
from domains.gateway.infrastructure.router_singleton import reload_router
from domains.tenancy.application.team_service import TeamService

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.identity.infrastructure.models.user import User

import pytest


async def setup_team_model(
    dev_client: AsyncClient,
    team_id: uuid.UUID,
    headers: dict[str, str],
    *,
    model_name: str,
    capability: str = "chat",
) -> None:
    cred_name = f"cred-{uuid.uuid4().hex[:6]}"
    r_cred = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/credentials",
        headers=headers,
        json={
            "provider": "openai",
            "name": cred_name,
            "api_key": "sk-multi-vkey-test-key-123456789",
            "scope": "team",
        },
    )
    assert r_cred.status_code == 201, r_cred.text
    cid = r_cred.json()["id"]
    r_model = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/models",
        headers=headers,
        json={
            "name": model_name,
            "capability": capability,
            "real_model": "gpt-4o-mini" if capability == "chat" else "text-embedding-3-small",
            "credential_id": cid,
            "provider": "openai",
        },
    )
    assert r_model.status_code == 201, r_model.text


async def setup_team_route(
    dev_client: AsyncClient,
    team_id: uuid.UUID,
    headers: dict[str, str],
    *,
    virtual_model: str,
    primary_model: str,
) -> None:
    r_route = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/routes",
        headers=headers,
        json={
            "virtual_model": virtual_model,
            "primary_models": [primary_model],
            "strategy": "simple-shuffle",
        },
    )
    assert r_route.status_code == 201, r_route.text


async def create_vkey_with_plain(
    dev_client: AsyncClient,
    team_id: uuid.UUID,
    headers: dict[str, str],
) -> tuple[str, str]:
    r = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/keys",
        headers=headers,
        json={"name": f"mvkey-{uuid.uuid4().hex[:8]}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["id"], body["plain_key"]


async def ensure_two_teams(
    db_session: AsyncSession,
    test_user: User,
) -> tuple[Any, Any]:
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()
    return primary, shared


async def ensure_homonym_slug_grant_teams(
    db_session: AsyncSession,
    test_user: User,
) -> tuple[Any, Any, Any, str]:
    """primary + 两个 grant team（不同 owner、相同 slug），test_user 为二者成员。

    Returns:
        (primary, grant_a, grant_b, homonym_slug)
    """
    from domains.identity.infrastructure.models.user import User

    homonym_slug = f"dup-{uuid.uuid4().hex[:8]}"
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    grant_a = await teams.create_team(
        name=f"grant-a-{uuid.uuid4().hex[:4]}",
        owner_user_id=test_user.id,
        slug=homonym_slug,
    )
    other = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hashed_password",
        name="Other Owner",
    )
    db_session.add(other)
    await db_session.flush()
    grant_b = await TeamService(db_session).create_team(
        name=f"grant-b-{uuid.uuid4().hex[:4]}",
        owner_user_id=other.id,
        slug=homonym_slug,
    )
    await teams.add_member(grant_b.id, test_user.id, "member")
    await db_session.commit()
    return primary, grant_a, grant_b, homonym_slug


def patch_router_acompletion(monkeypatch: pytest.MonkeyPatch, fake_response: Any) -> None:
    """Patch LiteLLM Router.acompletion（bound method 需接收 self）。"""

    async def _acompletion(_self: object, **_kwargs: object) -> Any:
        return fake_response

    monkeypatch.setattr("litellm.router.Router.acompletion", _acompletion)


async def backfill_self_grant_if_missing(
    db_session: AsyncSession,
    *,
    vkey_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await ensure_self_grant_for_vkey(
        db_session,
        vkey_id=vkey_id,
        tenant_id=tenant_id,
        granted_by_user_id=user_id,
    )
    await db_session.commit()
    await reload_router(db_session)
