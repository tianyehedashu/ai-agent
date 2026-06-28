"""``granted_route_selector_items`` — 共享路由在聊天选择器中的投影。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from domains.gateway.application.route import granted_route_selector_items as mod
from domains.gateway.application.route.granted_route_listing import GrantedRouteRow
from domains.gateway.application.route.granted_route_selector_items import (
    _representative_model,
    list_granted_route_selector_items,
)


def _model(name: str, *, tenant: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        tenant_id=tenant,
        provider="openai",
        real_model="gpt-4o-mini",
        capability="chat",
        tags={"display_name": name},
        last_test_status="success",
        enabled=True,
    )


def test_representative_prefers_first_resolvable_primary() -> None:
    owner = uuid.uuid4()
    pool = [_model("m-b", tenant=owner)]
    route = GrantedRouteRow(
        virtual_model="alias-x",
        primary_models=["team-slug/m-a", "team-slug/m-b"],
        tenant_id=owner,
    )
    rep = _representative_model(route, pool)
    assert rep is not None and rep.name == "m-b"


def test_representative_none_when_no_primary_in_pool() -> None:
    owner = uuid.uuid4()
    route = GrantedRouteRow(
        virtual_model="alias-x", primary_models=["missing"], tenant_id=owner
    )
    assert _representative_model(route, []) is None


def _patch_shared_team(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _shared_team(_self, _team_id: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(kind="shared")

    monkeypatch.setattr(
        "domains.tenancy.application.team_service.TeamService.get_team",
        _shared_team,
    )


@pytest.mark.asyncio
async def test_list_selector_items_projects_alias_and_marks_shared(monkeypatch) -> None:
    _patch_shared_team(monkeypatch)
    owner = uuid.uuid4()
    consumer = uuid.uuid4()
    row = GrantedRouteRow(
        virtual_model="exposed-alias", primary_models=["m-b"], tenant_id=owner
    )
    pool = [_model("m-b", tenant=owner)]

    async def _fake_rows(_session, _team_id, *, allowed):
        assert allowed is None
        return [row], [pool]

    monkeypatch.setattr(mod, "list_granted_route_rows_for_team", _fake_rows)

    items = await list_granted_route_selector_items(
        session=None,  # 未使用（已 monkeypatch）
        team_id=consumer,
        ability_filter=None,
    )
    assert len(items) == 1
    item = items[0]
    assert item["id"] == "exposed-alias"
    assert item["model_id"] == "exposed-alias"
    assert item["display_name"] == "exposed-alias"
    assert item["is_shared_route"] is True
    assert item["provider"] == "openai"


@pytest.mark.asyncio
async def test_list_selector_items_skips_personal_team(monkeypatch) -> None:
    called = False

    async def _should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        return [], []

    async def _personal_team(_self, _team_id: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(kind="personal")

    monkeypatch.setattr(mod, "list_granted_route_rows_for_team", _should_not_run)
    monkeypatch.setattr(
        "domains.tenancy.application.team_service.TeamService.get_team",
        _personal_team,
    )

    items = await list_granted_route_selector_items(
        session=None,
        team_id=uuid.uuid4(),
        ability_filter=None,
    )
    assert items == []
    assert called is False


@pytest.mark.asyncio
async def test_list_selector_items_applies_ability_filter(monkeypatch) -> None:
    _patch_shared_team(monkeypatch)
    owner = uuid.uuid4()
    row = GrantedRouteRow(
        virtual_model="exposed-alias", primary_models=["m-b"], tenant_id=owner
    )
    pool = [_model("m-b", tenant=owner)]

    async def _fake_rows(_session, _team_id, *, allowed):
        return [row], [pool]

    monkeypatch.setattr(mod, "list_granted_route_rows_for_team", _fake_rows)

    # chat 模型不应匹配 image_gen 能力筛选
    items = await list_granted_route_selector_items(
        session=None,
        team_id=uuid.uuid4(),
        ability_filter="image_gen",
    )
    assert items == []
