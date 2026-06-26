"""update_personal_model 能力编辑单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock
import uuid

import pytest

from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints
from domains.gateway.infrastructure.litellm_capability_hint_adapter import (
    LitellmCapabilityHintAdapter,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService


async def _seed_personal_model(
    db_session,
    test_user,
    *,
    capability: str = "chat",
    real_model: str = "volcengine/kimi-k2.6",
    provider: str = "volcengine",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred_id = uuid.uuid4()
    repo = GatewayModelRepository(db_session)
    row = await repo.create(
        tenant_id=team.id,
        name=f"my-kimi-{uuid.uuid4().hex[:6]}",
        capability=capability,
        real_model=real_model,
        credential_id=cred_id,
        provider=provider,
        tags={"display_name": "Kimi"},
    )
    await db_session.flush()
    user_id = test_user.id if isinstance(test_user.id, uuid.UUID) else uuid.UUID(str(test_user.id))
    return team.id, row.id, user_id


@pytest.mark.asyncio
async def test_update_personal_model_accepts_multiple_model_types(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    """个人模型编辑应与团队模型一致，支持多 model_type。"""
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    writes = GatewayManagementWriteService(db_session)

    def _vision_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints:
        _ = provider, real_model
        return LitellmModelInfoHints(supports_vision=True)

    monkeypatch.setattr(
        writes,
        "_assert_user_owns_credential",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))
    monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _vision_hints)

    updated = await writes.update_personal_model(
        user_uuid,
        model_id,
        fields={"model_types": ["text", "image"]},
    )
    assert updated.tags is not None
    assert updated.tags.get("supports_vision") is True
    assert updated.capability == "chat"


@pytest.mark.asyncio
async def test_update_personal_model_image_type_sets_vision_tag(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    writes = GatewayManagementWriteService(db_session)

    def _vision_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints:
        _ = provider, real_model
        return LitellmModelInfoHints(supports_vision=True)

    monkeypatch.setattr(
        writes,
        "_assert_user_owns_credential",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))
    monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _vision_hints)

    updated = await writes.update_personal_model(
        user_uuid,
        model_id,
        fields={"model_types": ["image"]},
    )
    assert updated.tags is not None
    assert updated.tags.get("supports_vision") is True

    repo = GatewayModelRepository(db_session)
    reloaded = await repo.get_for_tenant(model_id, tenant_id)
    assert reloaded is not None
    assert reloaded.tags.get("supports_vision") is True


@pytest.mark.asyncio
async def test_update_personal_model_weight_round_trips(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    """个人模型 weight 字段应能通过 update_personal_model 持久化，用于 weighted-pick 路由。"""
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    writes = GatewayManagementWriteService(db_session)

    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    updated = await writes.update_personal_model(user_uuid, model_id, fields={"weight": 7})
    assert updated.weight == 7

    repo = GatewayModelRepository(db_session)
    reloaded = await repo.get_for_tenant(model_id, tenant_id)
    assert reloaded is not None
    assert reloaded.weight == 7


@pytest.mark.asyncio
async def test_update_personal_model_rejects_non_positive_weight(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    from libs.exceptions import ValidationError

    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    writes = GatewayManagementWriteService(db_session)

    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    with pytest.raises(ValidationError):
        await writes.update_personal_model(user_uuid, model_id, fields={"weight": 0})
    with pytest.raises(ValidationError):
        await writes.update_personal_model(user_uuid, model_id, fields={"weight": "abc"})


@pytest.mark.asyncio
async def test_update_personal_model_renames_name(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    """个人模型应支持修改调用名称，并同步更新 vkey / 路由引用。"""
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    repo = GatewayModelRepository(db_session)
    existing = await repo.get_for_tenant(model_id, tenant_id)
    assert existing is not None
    writes = GatewayManagementWriteService(db_session)

    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    rename_spy = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(
        "domains.gateway.application.management.write_modules.model_writes.rename_gateway_model_name_references",
        rename_spy,
    )
    original_name = existing.name

    updated = await writes.update_personal_model(
        user_uuid, model_id, fields={"name": "my-new-call-name"}
    )
    assert updated.name == "my-new-call-name"
    rename_spy.assert_awaited_once()
    assert rename_spy.await_args.kwargs.get("tenant_id") == tenant_id
    assert rename_spy.await_args.kwargs.get("old_name") == original_name
    assert rename_spy.await_args.kwargs.get("new_name") == "my-new-call-name"


@pytest.mark.asyncio
async def test_update_personal_model_same_name_skips_rename_and_reload(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    """传入相同调用名称时不应触发引用重命名，也不应产生无意义的 UPDATE。"""
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    repo = GatewayModelRepository(db_session)
    existing = await repo.get_for_tenant(model_id, tenant_id)
    assert existing is not None
    writes = GatewayManagementWriteService(db_session)

    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    reload_spy = AsyncMock(return_value=None)
    monkeypatch.setattr(writes, "reload_litellm_router", reload_spy)
    rename_spy = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(
        "domains.gateway.application.management.write_modules.model_writes.rename_gateway_model_name_references",
        rename_spy,
    )

    updated = await writes.update_personal_model(
        user_uuid, model_id, fields={"name": existing.name}
    )
    assert updated.name == existing.name
    rename_spy.assert_not_awaited()
    reload_spy.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_personal_model_rejects_duplicate_name(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    """个人模型调用名称在同一租户内须唯一。"""
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    repo = GatewayModelRepository(db_session)
    existing = await repo.get_for_tenant(model_id, tenant_id)
    assert existing is not None
    await repo.create(
        tenant_id=tenant_id,
        name="existing-name",
        capability="chat",
        real_model="volcengine/kimi-k2.6",
        credential_id=existing.credential_id,
        provider=existing.provider,
        tags={"display_name": "Existing"},
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    from libs.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await writes.update_personal_model(
            user_uuid, model_id, fields={"name": "existing-name"}
        )


@pytest.mark.asyncio
async def test_update_personal_model_persists_context_window(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    writes = GatewayManagementWriteService(db_session)

    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    updated = await writes.update_personal_model(
        user_uuid,
        model_id,
        fields={"tags": {"context_window": 131072}},
    )
    assert updated.tags is not None
    assert updated.tags.get("context_window") == 131072

    repo = GatewayModelRepository(db_session)
    reloaded = await repo.get_for_tenant(model_id, tenant_id)
    assert reloaded is not None
    assert reloaded.tags.get("context_window") == 131072


@pytest.mark.asyncio
async def test_update_personal_model_clears_context_window(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    repo = GatewayModelRepository(db_session)
    existing = await repo.get_for_tenant(model_id, tenant_id)
    assert existing is not None
    await repo.update(
        model_id,
        tags={**(existing.tags or {}), "context_window": 65536},
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    updated = await writes.update_personal_model(
        user_uuid,
        model_id,
        fields={"tags": {"context_window": None}},
    )
    assert updated.tags is not None
    assert updated.tags.get("context_window") in (0, None)
