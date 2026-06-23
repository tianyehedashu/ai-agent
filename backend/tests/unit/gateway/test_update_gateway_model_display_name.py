"""update_gateway_model：display_name 写入 tags.display_name。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.management.write_modules.model_writes import (
    merge_display_name_into_tags,
)
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.exceptions import ValidationError
from tests.unit.gateway.credential_test_helpers import (
    create_tenant_test_credential,
    team_owner_actor_kw,
)


def test_merge_display_name_into_tags() -> None:
    assert merge_display_name_into_tags(None, None) is None
    assert merge_display_name_into_tags({"supports_vision": True}, None) == {
        "supports_vision": True
    }
    assert merge_display_name_into_tags(None, "  GPT-4o  ") == {"display_name": "GPT-4o"}
    merged = merge_display_name_into_tags({"supports_vision": True}, "通义 Max")
    assert merged == {"supports_vision": True, "display_name": "通义 Max"}


@pytest.mark.asyncio
async def test_update_gateway_model_display_name_only(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team.id, name="display-name-cred")
    repo = GatewayModelRepository(db_session)
    invoke_name = f"vm-{uuid.uuid4().hex[:6]}"
    row = await repo.create(
        tenant_id=team.id,
        name=invoke_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
        tags={"supports_vision": True},
    )
    writes = GatewayManagementWriteService(db_session)
    updated = await writes.update_gateway_model(
        row.id,
        tenant_id=team.id,
        is_platform_admin=False,
        fields={"display_name": "生产 GPT-4o Mini"},
        **team_owner_actor_kw(test_user),
    )
    assert updated.name == invoke_name
    assert updated.tags is not None
    assert updated.tags.get("display_name") == "生产 GPT-4o Mini"
    assert updated.tags.get("supports_vision") is True


@pytest.mark.asyncio
async def test_update_gateway_model_rejects_empty_display_name(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team.id, name="display-empty-cred")
    repo = GatewayModelRepository(db_session)
    row = await repo.create(
        tenant_id=team.id,
        name=f"vm-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError, match="显示名不能为空"):
        await writes.update_gateway_model(
            row.id,
            tenant_id=team.id,
            is_platform_admin=False,
            fields={"display_name": "   "},
            **team_owner_actor_kw(test_user),
        )
