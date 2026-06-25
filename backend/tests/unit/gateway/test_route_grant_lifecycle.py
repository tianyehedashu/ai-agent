"""路由共享授权生命周期：成员移除 / 团队删除 / 路由删除级联撤销。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.infrastructure.repositories.gateway_route_grant_repository import (
    GatewayRouteTeamGrantRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayRouteRepository,
)
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


async def _seed_route(db_session, owner_id) -> uuid.UUID:
    owner_team = await TeamService(db_session).ensure_personal_team(owner_id)
    route = await GatewayRouteRepository(db_session).create(
        tenant_id=owner_team.id,
        virtual_model=f"route-{uuid.uuid4().hex[:6]}",
        primary_models=["m1"],
        created_by_user_id=owner_id,
    )
    await db_session.flush()
    return route.id


@pytest.mark.asyncio
async def test_remove_member_revokes_route_grants(db_session, test_user) -> None:
    teams = TeamService(db_session)
    route_id = await _seed_route(db_session, test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}", owner_user_id=test_user.id
    )
    await teams.add_member(shared.id, test_user.id, "member")
    repo = GatewayRouteTeamGrantRepository(db_session)
    await repo.upsert_active(
        route_id=route_id,
        tenant_id=shared.id,
        exposed_alias=f"a-{uuid.uuid4().hex[:6]}",
        granted_by_user_id=test_user.id,
    )
    await db_session.flush()

    assert await repo.get_active(route_id, shared.id) is not None
    await teams.remove_member(shared.id, test_user.id)
    await db_session.flush()
    assert await repo.get_active(route_id, shared.id) is None


@pytest.mark.asyncio
async def test_membership_revoke_invalidates_consumer_tenant_cache(
    db_session, test_user, monkeypatch
) -> None:
    from domains.gateway.application.management.route_team_grant_lifecycle import (
        revoke_route_grants_for_user_team_membership,
    )

    teams = TeamService(db_session)
    route_id = await _seed_route(db_session, test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}", owner_user_id=test_user.id
    )
    await GatewayRouteTeamGrantRepository(db_session).upsert_active(
        route_id=route_id,
        tenant_id=shared.id,
        exposed_alias=f"a-{uuid.uuid4().hex[:6]}",
        granted_by_user_id=test_user.id,
    )
    await db_session.flush()

    invalidated: list[uuid.UUID] = []

    def _capture(tenant_id: uuid.UUID) -> None:
        invalidated.append(tenant_id)

    monkeypatch.setattr(
        "domains.gateway.application.management.route_team_grant_lifecycle."
        "invalidate_gateway_read_caches_for_tenant",
        _capture,
    )
    count = await revoke_route_grants_for_user_team_membership(
        db_session,
        user_id=test_user.id,
        tenant_id=shared.id,
    )
    assert count == 1
    assert invalidated == [shared.id]


@pytest.mark.asyncio
async def test_delete_shared_team_revokes_route_grants(db_session, test_user) -> None:
    teams = TeamService(db_session)
    route_id = await _seed_route(db_session, test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}", owner_user_id=test_user.id
    )
    repo = GatewayRouteTeamGrantRepository(db_session)
    await repo.upsert_active(
        route_id=route_id,
        tenant_id=shared.id,
        exposed_alias=f"a-{uuid.uuid4().hex[:6]}",
        granted_by_user_id=test_user.id,
    )
    await db_session.flush()

    await teams.delete_shared_team(shared.id)
    await db_session.flush()
    assert await repo.get_active(route_id, shared.id) is None


@pytest.mark.asyncio
async def test_revoke_for_route_deleted_cascades(db_session, test_user) -> None:
    teams = TeamService(db_session)
    route_id = await _seed_route(db_session, test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}", owner_user_id=test_user.id
    )
    repo = GatewayRouteTeamGrantRepository(db_session)
    await repo.upsert_active(
        route_id=route_id,
        tenant_id=shared.id,
        exposed_alias=f"a-{uuid.uuid4().hex[:6]}",
        granted_by_user_id=test_user.id,
    )
    await db_session.flush()

    revoked = await repo.revoke_all_for_route(route_id)
    assert revoked == 1
    assert await repo.get_active(route_id, shared.id) is None


@pytest.mark.asyncio
async def test_membership_loss_only_revokes_own_grants(db_session, test_user) -> None:
    """只撤销"被移除成员共享进来"的 grant，他人 grant 不受影响。"""
    teams = TeamService(db_session)
    other = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        name="Other",
    )
    db_session.add(other)
    await db_session.flush()

    my_route = await _seed_route(db_session, test_user.id)
    other_route = await _seed_route(db_session, other.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}", owner_user_id=other.id
    )
    await teams.add_member(shared.id, test_user.id, "member")
    repo = GatewayRouteTeamGrantRepository(db_session)
    await repo.upsert_active(
        route_id=my_route,
        tenant_id=shared.id,
        exposed_alias=f"mine-{uuid.uuid4().hex[:6]}",
        granted_by_user_id=test_user.id,
    )
    await repo.upsert_active(
        route_id=other_route,
        tenant_id=shared.id,
        exposed_alias=f"theirs-{uuid.uuid4().hex[:6]}",
        granted_by_user_id=other.id,
    )
    await db_session.flush()

    await teams.remove_member(shared.id, test_user.id)
    await db_session.flush()

    assert await repo.get_active(my_route, shared.id) is None
    assert await repo.get_active(other_route, shared.id) is not None


@pytest.mark.asyncio
async def test_tenant_reload_invalidates_consumer_resolve_cache(
    db_session, test_user, monkeypatch
) -> None:
    """owner 侧租户级 reload 须连带失效持有共享路由的消费团队 resolve 缓存（Bug2）。

    委派结果按消费团队键 ``(T, user, alias)`` 缓存；owner 改/禁用底层模型时 reload 只
    失效 owner 租户，遗漏 T。验证连带失效覆盖 T。
    """
    from bootstrap.config import settings
    from domains.gateway.application.management.write_modules._base import (
        GatewayManagementWriteBaseMixin,
    )
    from domains.gateway.application.resolve_model_cache import (
        CACHE_MISS,
        clear_resolve_model_cache_for_tests,
        peek_resolve_cache_entry,
        put_resolve_cache_entry,
    )

    monkeypatch.setattr(settings, "gateway_route_sharing_enabled", True)
    clear_resolve_model_cache_for_tests()

    teams = TeamService(db_session)
    owner_team = await teams.ensure_personal_team(test_user.id)
    route_id = await _seed_route(db_session, test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}", owner_user_id=test_user.id
    )
    alias = f"a-{uuid.uuid4().hex[:6]}"
    await GatewayRouteTeamGrantRepository(db_session).upsert_active(
        route_id=route_id,
        tenant_id=shared.id,
        exposed_alias=alias,
        granted_by_user_id=test_user.id,
    )
    await db_session.flush()

    # 消费团队侧委派缓存条目（用负缓存标记即可区分"存在 vs 失效"）
    put_resolve_cache_entry(shared.id, alias, user_id=None, resolved=None)
    assert peek_resolve_cache_entry(shared.id, alias, user_id=None) is None

    svc = GatewayManagementWriteBaseMixin(db_session)
    await svc._invalidate_shared_route_consumer_caches(exclude=owner_team.id)

    assert peek_resolve_cache_entry(shared.id, alias, user_id=None) is CACHE_MISS
