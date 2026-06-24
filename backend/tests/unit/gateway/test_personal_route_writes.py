"""personal 虚拟路由写侧校验（跨 team primary_models）。"""

from __future__ import annotations

from unittest.mock import AsyncMock
import uuid

import pytest

from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.exceptions import ValidationError
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


@pytest.mark.asyncio
async def test_create_personal_route_accepts_cross_team_primary(
    db_session, test_user, monkeypatch
) -> None:
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"WriteCross-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()
    await db_session.refresh(shared)

    shared_cred = await create_tenant_test_credential(
        db_session, shared.id, name=f"write-cross-{uuid.uuid4().hex[:6]}"
    )
    model_name = f"shared-model-{uuid.uuid4().hex[:6]}"
    await GatewayModelRepository(db_session).create(
        tenant_id=shared.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=shared_cred.id,
        provider="openai",
    )
    await db_session.flush()

    route_ref = f"{shared.slug}/{model_name}"
    virtual = f"vr-write-{uuid.uuid4().hex[:6]}"
    writes = GatewayManagementWriteService(db_session)
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    route = await writes.create_gateway_route(
        tenant_id=personal.id,
        virtual_model=virtual,
        primary_models=[route_ref],
        fallbacks_general=[],
        fallbacks_content_policy=[],
        fallbacks_context_window=[],
        strategy="simple-shuffle",
        retry_policy=None,
        actor_user_id=test_user.id,
    )
    assert route_ref in route.primary_models


@pytest.mark.asyncio
async def test_create_personal_route_rejects_unknown_cross_team_ref(
    db_session, test_user, monkeypatch
) -> None:
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    with pytest.raises(ValidationError, match="未注册或不可引用"):
        await writes.create_gateway_route(
            tenant_id=personal.id,
            virtual_model=f"vr-bad-{uuid.uuid4().hex[:6]}",
            primary_models=["no-such-team/model-name"],
            fallbacks_general=[],
            fallbacks_content_policy=[],
            fallbacks_context_window=[],
            strategy="simple-shuffle",
            retry_policy=None,
            actor_user_id=test_user.id,
        )


@pytest.mark.asyncio
async def test_create_shared_team_route_rejects_other_team_primary(
    db_session, test_user, monkeypatch
) -> None:
    """协作团队路由仍只允许本 tenant 模型名（不含 slug 前缀）。"""
    teams = TeamService(db_session)
    shared_a = await teams.create_team(
        name=f"RouteA-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    shared_b = await teams.create_team(
        name=f"RouteB-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()
    await db_session.refresh(shared_b)

    cred_b = await create_tenant_test_credential(
        db_session, shared_b.id, name=f"team-b-{uuid.uuid4().hex[:6]}"
    )
    model_name = f"team-b-model-{uuid.uuid4().hex[:6]}"
    await GatewayModelRepository(db_session).create(
        tenant_id=shared_b.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred_b.id,
        provider="openai",
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    with pytest.raises(ValidationError, match="未注册的模型别名"):
        await writes.create_gateway_route(
            tenant_id=shared_a.id,
            virtual_model=f"vr-team-{uuid.uuid4().hex[:6]}",
            primary_models=[f"{shared_b.slug}/{model_name}"],
            fallbacks_general=[],
            fallbacks_content_policy=[],
            fallbacks_context_window=[],
            strategy="simple-shuffle",
            retry_policy=None,
            actor_user_id=test_user.id,
        )
