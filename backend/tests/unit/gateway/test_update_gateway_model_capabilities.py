"""update_gateway_model 能力编辑（capability / model_types / 路由校验）。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.gateway_route_repository import (
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.exceptions import ValidationError
from tests.unit.gateway.credential_test_helpers import (
    create_tenant_test_credential,
    team_owner_actor_kw,
)


async def _seed_team_chat_models(
    db_session,
    test_user,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str, str]:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team.id, name="cap-edit-cred")
    repo = GatewayModelRepository(db_session)
    name_a = f"vm-a-{uuid.uuid4().hex[:6]}"
    name_b = f"vm-b-{uuid.uuid4().hex[:6]}"
    model_a = await repo.create(
        tenant_id=team.id,
        name=name_a,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
        tags={"supports_vision": False},
    )
    model_b = await repo.create(
        tenant_id=team.id,
        name=name_b,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    route_repo = GatewayRouteRepository(db_session)
    await route_repo.create(
        tenant_id=team.id,
        virtual_model=f"route-{uuid.uuid4().hex[:6]}",
        primary_models=[name_a, name_b],
    )
    await db_session.flush()
    return team.id, model_a.id, model_b.id, name_a, name_b


@pytest.mark.asyncio
async def test_update_gateway_model_model_types_sets_vision_tag(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team.id, name="vision-cred")
    repo = GatewayModelRepository(db_session)
    row = await repo.create(
        tenant_id=team.id,
        name=f"vm-vision-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
        tags={},
    )
    writes = GatewayManagementWriteService(db_session)
    updated = await writes.update_gateway_model(
        row.id,
        tenant_id=team.id,
        is_platform_admin=False,
        fields={"model_types": ["text", "image"]},
        **team_owner_actor_kw(test_user),
    )
    assert updated.tags is not None
    assert updated.tags.get("supports_vision") is True


@pytest.mark.asyncio
async def test_update_gateway_model_capability_rejected_when_route_siblings_differ(
    db_session, test_user
) -> None:
    team_id, model_a_id, _model_b_id, _name_a, _name_b = await _seed_team_chat_models(
        db_session, test_user
    )
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError, match="capability 须一致"):
        await writes.update_gateway_model(
            model_a_id,
            tenant_id=team_id,
            is_platform_admin=False,
            fields={"capability": "embedding"},
            **team_owner_actor_kw(test_user),
        )


@pytest.mark.asyncio
async def test_update_gateway_model_rejects_image_gen_on_chat_capability(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team.id, name="chat-cap-cred")
    repo = GatewayModelRepository(db_session)
    row = await repo.create(
        tenant_id=team.id,
        name=f"vm-chat-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError, match="capability='chat'"):
        await writes.update_gateway_model(
            row.id,
            tenant_id=team.id,
            is_platform_admin=False,
            fields={"model_types": ["image_gen"]},
            **team_owner_actor_kw(test_user),
        )


@pytest.mark.asyncio
async def test_update_gateway_model_rejects_volcengine_image_without_endpoint(
    db_session, test_user
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session,
        team.id,
        name="volc-img-cred",
        provider="volcengine",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        extra={"region": "cn-beijing"},
    )
    repo = GatewayModelRepository(db_session)
    row = await repo.create(
        tenant_id=team.id,
        name=f"vm-volc-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="volcengine/doubao-seedream-4-5-251128",
        credential_id=cred.id,
        provider="volcengine",
    )
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError, match="image_endpoint_id"):
        await writes.update_gateway_model(
            row.id,
            tenant_id=team.id,
            is_platform_admin=False,
            fields={"capability": "image", "model_types": ["image_gen"]},
            **team_owner_actor_kw(test_user),
        )
