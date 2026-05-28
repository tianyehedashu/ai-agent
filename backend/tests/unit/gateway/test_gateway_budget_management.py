"""Gateway 预算列表与删除归属校验单测。"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.application.management.write_modules import (
    GatewayManagementWriteService,
)
from domains.gateway.domain.errors import ManagementEntityNotFoundError


@pytest.mark.asyncio
async def test_list_budgets_for_tenant_and_user_includes_visible_key_budgets() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    key_id = uuid.uuid4()
    tenant_budget = SimpleNamespace(id=uuid.uuid4(), target_kind="tenant")
    user_budget = SimpleNamespace(id=uuid.uuid4(), target_kind="user")
    key_budget = SimpleNamespace(id=uuid.uuid4(), target_kind="key")

    svc._budgets.list_for_target = AsyncMock(
        side_effect=lambda kind, tid: {
            ("tenant", tenant_id): [tenant_budget],
            ("user", user_id): [user_budget],
        }.get((kind, tid), [])
    )
    svc._vkeys.list_for_tenant = AsyncMock(
        return_value=[SimpleNamespace(id=key_id, created_by_user_id=user_id, is_system=False)]
    )
    svc._budgets.list_for_target_ids = AsyncMock(return_value=[key_budget])

    rows = await svc.list_budgets_for_tenant_and_user(tenant_id, user_id, actor_user_id=user_id)

    assert rows == [tenant_budget, user_budget, key_budget]
    svc._budgets.list_for_target_ids.assert_awaited_once_with("key", [key_id])


@pytest.mark.asyncio
async def test_list_budgets_for_team_admin_merges_all_scopes() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    tenant_id = uuid.uuid4()
    member_id = uuid.uuid4()
    key_id = uuid.uuid4()
    tenant_budget = SimpleNamespace(id=uuid.uuid4(), target_kind="tenant", model_name=None)
    user_budget = SimpleNamespace(id=uuid.uuid4(), target_kind="user", model_name="gpt-4")
    key_budget = SimpleNamespace(id=uuid.uuid4(), target_kind="key", model_name=None)
    system_budget = SimpleNamespace(id=uuid.uuid4(), target_kind="system", model_name=None)

    svc._budgets.list_for_target = AsyncMock(
        side_effect=lambda kind, tid: {
            ("tenant", tenant_id): [tenant_budget],
            ("system", None): [system_budget],
        }.get((kind, tid), [])
    )
    svc._teams.list_team_members = AsyncMock(return_value=[SimpleNamespace(user_id=member_id)])
    svc._vkeys.list_for_tenant = AsyncMock(return_value=[SimpleNamespace(id=key_id)])
    svc._budgets.list_for_target_ids = AsyncMock(
        side_effect=lambda kind, _ids: {
            "user": [user_budget],
            "key": [key_budget],
        }.get(kind, [])
    )

    rows = await svc.list_budgets_for_team_admin(
        tenant_id,
        include_system=True,
    )

    assert rows == [tenant_budget, user_budget, key_budget, system_budget]


@pytest.mark.asyncio
async def test_list_budgets_for_team_admin_filters_target_kind_and_model() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    tenant_id = uuid.uuid4()
    matching = SimpleNamespace(id=uuid.uuid4(), target_kind="user", model_name="claude-3")
    other = SimpleNamespace(id=uuid.uuid4(), target_kind="user", model_name="gpt-4")

    svc._budgets.list_for_target = AsyncMock(return_value=[])
    svc._teams.list_team_members = AsyncMock(return_value=[SimpleNamespace(user_id=uuid.uuid4())])
    svc._vkeys.list_for_tenant = AsyncMock(return_value=[])
    svc._budgets.list_for_target_ids = AsyncMock(return_value=[matching, other])

    rows = await svc.list_budgets_for_team_admin(
        tenant_id,
        target_kind="user",
        model_name="claude-3",
    )

    assert rows == [matching]


@pytest.mark.asyncio
async def test_delete_budget_rejects_cross_tenant() -> None:
    session = MagicMock()
    writes = GatewayManagementWriteService(session)
    budget_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    other_tenant = uuid.uuid4()

    writes._budgets.get = AsyncMock(
        return_value=SimpleNamespace(
            id=budget_id,
            target_kind="tenant",
            target_id=other_tenant,
        )
    )
    writes._teams.list_team_members = AsyncMock(return_value=[])
    writes._budgets.delete = AsyncMock(return_value=True)

    with pytest.raises(ManagementEntityNotFoundError):
        await writes.delete_budget(
            budget_id,
            tenant_id=tenant_id,
            is_platform_admin=False,
        )

    writes._budgets.delete.assert_not_called()
    writes._teams.list_team_members.assert_not_called()


@pytest.mark.asyncio
async def test_delete_budget_allows_tenant_budget() -> None:
    session = MagicMock()
    writes = GatewayManagementWriteService(session)
    budget_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    writes._budgets.get = AsyncMock(
        return_value=SimpleNamespace(
            id=budget_id,
            target_kind="tenant",
            target_id=tenant_id,
        )
    )
    writes._teams.list_team_members = AsyncMock(return_value=[])
    writes._budgets.delete = AsyncMock(return_value=True)

    await writes.delete_budget(
        budget_id,
        tenant_id=tenant_id,
        is_platform_admin=False,
    )

    writes._budgets.delete.assert_awaited_once_with(budget_id)
    writes._teams.list_team_members.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_budget_rejects_cross_tenant_user_target() -> None:
    session = MagicMock()
    writes = GatewayManagementWriteService(session)
    tenant_id = uuid.uuid4()
    outsider_id = uuid.uuid4()

    writes._teams.list_team_members = AsyncMock(
        return_value=[SimpleNamespace(user_id=uuid.uuid4())]
    )
    writes._budgets.upsert = AsyncMock()

    with pytest.raises(ManagementEntityNotFoundError):
        await writes.upsert_budget(
            target_kind="user",
            target_id=outsider_id,
            period="monthly",
            model_name=None,
            limit_usd=None,
            soft_limit_usd=None,
            limit_tokens=None,
            limit_requests=None,
            tenant_id=tenant_id,
            is_platform_admin=False,
        )

    writes._budgets.upsert.assert_not_called()
    writes._teams.list_team_members.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_budget_allows_tenant_target() -> None:
    session = MagicMock()
    writes = GatewayManagementWriteService(session)
    tenant_id = uuid.uuid4()
    saved = SimpleNamespace(id=uuid.uuid4())

    writes._teams.list_team_members = AsyncMock(return_value=[])
    writes._budgets.upsert = AsyncMock(return_value=saved)

    result = await writes.upsert_budget(
        target_kind="tenant",
        target_id=tenant_id,
        period="monthly",
        model_name=None,
        limit_usd=Decimal("10"),
        soft_limit_usd=None,
        limit_tokens=None,
        limit_requests=None,
        tenant_id=tenant_id,
        is_platform_admin=False,
    )

    assert result is saved
    writes._budgets.upsert.assert_awaited_once()
    writes._teams.list_team_members.assert_not_called()
