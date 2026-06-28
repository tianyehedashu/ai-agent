"""personal_route_callable_reads 聚合读侧单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.route.management.personal_route_callable_reads import (
    build_personal_route_allowed_refs,
    collect_personal_route_callable_candidates,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


@pytest.mark.asyncio
async def test_collect_includes_cross_team_route_ref(db_session, test_user) -> None:
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"CallableCross-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()
    await db_session.refresh(shared)

    shared_cred = await create_tenant_test_credential(
        db_session, shared.id, name=f"callable-{uuid.uuid4().hex[:6]}"
    )
    model_name = f"callable-model-{uuid.uuid4().hex[:6]}"
    await GatewayModelRepository(db_session).create(
        tenant_id=shared.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=shared_cred.id,
        provider="openai",
    )
    await db_session.flush()

    expected_ref = f"{shared.slug}/{model_name}"
    candidates = await collect_personal_route_callable_candidates(
        db_session,
        user_id=test_user.id,
        is_platform_admin=False,
    )
    refs = {c.route_ref for c in candidates}
    assert expected_ref in refs

    matching = next(c for c in candidates if c.route_ref == expected_ref)
    assert matching.team_kind == "shared"
    assert matching.tenant_id == shared.id


@pytest.mark.asyncio
async def test_build_allowed_refs_contains_cross_team_entry(db_session, test_user) -> None:
    teams = TeamService(db_session)
    await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"AllowedRef-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()
    await db_session.refresh(shared)

    shared_cred = await create_tenant_test_credential(
        db_session, shared.id, name=f"allowed-{uuid.uuid4().hex[:6]}"
    )
    model_name = f"allowed-model-{uuid.uuid4().hex[:6]}"
    await GatewayModelRepository(db_session).create(
        tenant_id=shared.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=shared_cred.id,
        provider="openai",
    )
    await db_session.flush()

    allowed = await build_personal_route_allowed_refs(
        db_session,
        user_id=test_user.id,
        is_platform_admin=False,
    )
    assert f"{shared.slug}/{model_name}" in allowed
