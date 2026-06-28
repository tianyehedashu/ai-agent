"""跨团队共享路由（委派）：解析 swap、Router 名对齐、grant deployment 装配。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.catalog.model_or_route_resolution import (
    ResolvedModelName,
    resolve_model_or_route,
)
from domains.gateway.application.grant.resolve_model_cache import (
    clear_resolve_model_cache_for_tests,
)
from domains.gateway.application.route.router_model_name import router_model_name_for_client
from domains.gateway.domain.route.router_model_name import encode_router_model_name
from domains.gateway.infrastructure.repositories.gateway_route_grant_repository import (
    GatewayRouteTeamGrantRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.tenancy.application.team_service import TeamService
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential

# ───────────────────────── 委派解析（DB） ─────────────────────────


@pytest.mark.asyncio
async def test_delegated_route_resolves_under_owner(db_session, test_user, monkeypatch) -> None:
    monkeypatch.setattr(settings, "gateway_resolve_model_cache_enabled", False)
    monkeypatch.setattr(settings, "gateway_route_sharing_enabled", True)
    clear_resolve_model_cache_for_tests()

    owner_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session, owner_team.id, name=f"deleg-{uuid.uuid4().hex[:6]}"
    )
    model_name = f"m-{uuid.uuid4().hex[:6]}"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=owner_team.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    route = await GatewayRouteRepository(db_session).create(
        tenant_id=owner_team.id,
        virtual_model=f"route-{uuid.uuid4().hex[:6]}",
        primary_models=[model_name],
        created_by_user_id=test_user.id,
    )
    shared = await TeamService(db_session).create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    alias = f"alias-{uuid.uuid4().hex[:6]}"
    await GatewayRouteTeamGrantRepository(db_session).upsert_active(
        route_id=route.id,
        tenant_id=shared.id,
        exposed_alias=alias,
        granted_by_user_id=test_user.id,
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, shared.id, alias, user_id=None)
    assert resolved is not None
    assert resolved.delegated_grant_team_id == shared.id
    assert resolved.exposed_alias == alias
    assert resolved.record.id == model.id  # owner 模型（owner 凭据上游）
    assert resolved.route is not None and resolved.route.id == route.id


@pytest.mark.asyncio
async def test_delegated_route_fail_closed_without_owner(
    db_session, test_user, monkeypatch
) -> None:
    """created_by_user_id 缺失（历史未回填）时委派 fail-closed。"""
    monkeypatch.setattr(settings, "gateway_resolve_model_cache_enabled", False)
    monkeypatch.setattr(settings, "gateway_route_sharing_enabled", True)
    clear_resolve_model_cache_for_tests()

    owner_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session, owner_team.id, name=f"noowner-{uuid.uuid4().hex[:6]}"
    )
    model_name = f"m-{uuid.uuid4().hex[:6]}"
    await GatewayModelRepository(db_session).create(
        tenant_id=owner_team.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    route = await GatewayRouteRepository(db_session).create(
        tenant_id=owner_team.id,
        virtual_model=f"route-{uuid.uuid4().hex[:6]}",
        primary_models=[model_name],
        created_by_user_id=None,
    )
    shared = await TeamService(db_session).create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    alias = f"alias-{uuid.uuid4().hex[:6]}"
    await GatewayRouteTeamGrantRepository(db_session).upsert_active(
        route_id=route.id,
        tenant_id=shared.id,
        exposed_alias=alias,
        granted_by_user_id=test_user.id,
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, shared.id, alias, user_id=None)
    assert resolved is None


@pytest.mark.asyncio
async def test_route_sharing_flag_off_disables_delegation(
    db_session, test_user, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "gateway_resolve_model_cache_enabled", False)
    monkeypatch.setattr(settings, "gateway_route_sharing_enabled", False)
    clear_resolve_model_cache_for_tests()

    owner_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session, owner_team.id, name=f"flag-{uuid.uuid4().hex[:6]}"
    )
    model_name = f"m-{uuid.uuid4().hex[:6]}"
    await GatewayModelRepository(db_session).create(
        tenant_id=owner_team.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    route = await GatewayRouteRepository(db_session).create(
        tenant_id=owner_team.id,
        virtual_model=f"route-{uuid.uuid4().hex[:6]}",
        primary_models=[model_name],
        created_by_user_id=test_user.id,
    )
    shared = await TeamService(db_session).create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    alias = f"alias-{uuid.uuid4().hex[:6]}"
    await GatewayRouteTeamGrantRepository(db_session).upsert_active(
        route_id=route.id,
        tenant_id=shared.id,
        exposed_alias=alias,
        granted_by_user_id=test_user.id,
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, shared.id, alias, user_id=None)
    assert resolved is None


# ───────────────────────── Router 名对齐（纯函数） ─────────────────────────


def test_router_model_name_for_delegated_uses_consumer_team() -> None:
    consumer = uuid.uuid4()
    owner = uuid.uuid4()
    route = SimpleNamespace(tenant_id=owner, virtual_model="vm")
    resolved = ResolvedModelName(
        record=SimpleNamespace(tenant_id=owner),
        route=route,
        via_route="vm",
        delegated_grant_team_id=consumer,
        exposed_alias="alias-x",
    )
    encoded = router_model_name_for_client(consumer, "alias-x", resolved)
    # 关键：deployment 注册在消费团队命名空间 → 编码须用 consumer + 别名
    assert encoded == encode_router_model_name(consumer, "alias-x")


# ───────────────────── grant deployment 装配（monkeypatch crypto） ─────────────────


@dataclass
class _FakeModel:
    name: str
    tenant_id: uuid.UUID
    credential_id: uuid.UUID
    provider: str = "openai"
    real_model: str = "gpt-4o-mini"
    capability: str = "chat"
    weight: int = 1
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    tags: dict | None = None
    upstream_call_shape: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class _FakeRoute:
    id: uuid.UUID
    tenant_id: uuid.UUID
    virtual_model: str
    primary_models: list[str]
    enabled: bool = True
    retry_policy: dict | None = None
    fallbacks_general: list[str] = field(default_factory=list)
    fallbacks_content_policy: list[str] = field(default_factory=list)
    fallbacks_context_window: list[str] = field(default_factory=list)


@dataclass
class _FakeGrant:
    route_id: uuid.UUID
    tenant_id: uuid.UUID
    exposed_alias: str


def test_grants_to_virtual_deployments_encodes_consumer_namespace(monkeypatch) -> None:
    from domains.gateway.infrastructure.litellm import router_singleton as rs

    captured: list[str] = []

    def _fake_build_deployment(*, model_name, src, cred, **_kw):
        captured.append(model_name)
        return {"model_name": model_name, "model_info": {"id": str(src.id)}}

    monkeypatch.setattr(rs, "_build_deployment", _fake_build_deployment)

    owner = uuid.uuid4()
    consumer = uuid.uuid4()
    cid = uuid.uuid4()
    model = _FakeModel(name="m1", tenant_id=owner, credential_id=cid)
    route = _FakeRoute(id=uuid.uuid4(), tenant_id=owner, virtual_model="vm", primary_models=["m1"])
    grant = _FakeGrant(route_id=route.id, tenant_id=consumer, exposed_alias="alias-x")

    deployments = rs._grants_to_virtual_deployments(
        [grant],
        {route.id: route},
        [model],
        {cid: SimpleNamespace(id=cid)},
        None,
        route_slug_contexts={},
    )
    assert len(deployments) == 1
    assert captured == [encode_router_model_name(consumer, "alias-x")]


def test_grants_skip_disabled_or_missing_route(monkeypatch) -> None:
    from domains.gateway.infrastructure.litellm import router_singleton as rs

    monkeypatch.setattr(rs, "_build_deployment", lambda **_kw: {"model_name": "x"})
    consumer = uuid.uuid4()
    owner = uuid.uuid4()
    disabled = _FakeRoute(
        id=uuid.uuid4(),
        tenant_id=owner,
        virtual_model="vm",
        primary_models=["m1"],
        enabled=False,
    )
    grant_disabled = _FakeGrant(route_id=disabled.id, tenant_id=consumer, exposed_alias="a1")
    grant_missing = _FakeGrant(route_id=uuid.uuid4(), tenant_id=consumer, exposed_alias="a2")
    deployments = rs._grants_to_virtual_deployments(
        [grant_disabled, grant_missing],
        {disabled.id: disabled},
        [],
        {},
        None,
        route_slug_contexts={},
    )
    assert deployments == []


def test_build_route_list_item_resolves_slug_prefixed_primary() -> None:
    from datetime import UTC, datetime

    from domains.gateway.application.proxy.proxy_model_list_reads import (
        _build_route_model_list_item,
    )
    from domains.gateway.application.route.granted_route_listing import GrantedRouteRow
    from domains.gateway.application.route.route_owner_slug_maps import RouteOwnerSlugContext

    owner = uuid.uuid4()
    shared = uuid.uuid4()
    slug = "shared-team"
    now = datetime.now(UTC)
    row = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=shared,
        name="my-model",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=uuid.uuid4(),
        provider="openai",
        tags={},
        created_at=now,
        last_tested_at=None,
        last_test_status=None,
    )
    pool_index = {(str(shared), "my-model"): row}
    route = GrantedRouteRow(
        virtual_model="shared-alias",
        primary_models=[f"{slug}/my-model"],
        tenant_id=owner,
    )
    item = _build_route_model_list_item(
        route,
        models_by_name={},
        entitlement_by_name={"my-model": "active"},
        slug_ctx=RouteOwnerSlugContext(
            slug_to_tenant={slug: shared},
            enable_slug_prefix=True,
        ),
        models_by_team_name=pool_index,
        route_owner_tenant_id=owner,
    )
    assert item is not None
    assert item["id"] == "shared-alias"
    assert item["gateway"]["real_model"] == "gpt-4o-mini"
