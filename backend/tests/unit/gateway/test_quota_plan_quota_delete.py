"""plan 配额单条删除写路径单测。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.write_modules import GatewayManagementWriteService
from libs.exceptions import NotFoundError, PermissionDeniedError


def _writes() -> GatewayManagementWriteService:
    svc = GatewayManagementWriteService(MagicMock())
    svc._session.commit = AsyncMock()  # type: ignore[method-assign]
    svc._invalidate_quota_rule_list_cache = AsyncMock()  # type: ignore[method-assign]
    return svc


@pytest.mark.asyncio
async def test_delete_upstream_plan_quota_removes_empty_plan() -> None:
    """删除最后一条上游配额后连带删除空套餐，并失效列表缓存。"""
    svc = _writes()
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    svc._provider_plans.get = AsyncMock(return_value=MagicMock(credential_id=cred_id))  # type: ignore[method-assign]
    svc._assert_upstream_credential_writable = AsyncMock(return_value=tenant_id)  # type: ignore[method-assign]
    svc._provider_plans.delete_quota = AsyncMock(return_value=True)  # type: ignore[method-assign]
    svc._provider_plans.list_quotas = AsyncMock(return_value=[])  # type: ignore[method-assign]
    svc._provider_plans.delete = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await svc.delete_plan_quota(
        layer="upstream",
        plan_id=plan_id,
        quota_id=quota_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        is_platform_admin=False,
        is_team_admin=True,
    )

    svc._provider_plans.delete_quota.assert_awaited_once_with(plan_id, quota_id)
    svc._provider_plans.delete.assert_awaited_once_with(plan_id)
    svc._invalidate_quota_rule_list_cache.assert_awaited_once()
    assert svc._invalidate_quota_rule_list_cache.await_args.kwargs["upstream_changed"] is True


@pytest.mark.asyncio
async def test_delete_upstream_plan_quota_keeps_plan_with_remaining_quotas() -> None:
    """仍有其它配额时只删该条，不动套餐。"""
    svc = _writes()
    plan_id = uuid.uuid4()

    svc._provider_plans.get = AsyncMock(return_value=MagicMock(credential_id=uuid.uuid4()))  # type: ignore[method-assign]
    svc._assert_upstream_credential_writable = AsyncMock(return_value=uuid.uuid4())  # type: ignore[method-assign]
    svc._provider_plans.delete_quota = AsyncMock(return_value=True)  # type: ignore[method-assign]
    svc._provider_plans.list_quotas = AsyncMock(return_value=[MagicMock()])  # type: ignore[method-assign]
    svc._provider_plans.delete = AsyncMock()  # type: ignore[method-assign]

    await svc.delete_plan_quota(
        layer="upstream",
        plan_id=plan_id,
        quota_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        is_platform_admin=True,
        is_team_admin=False,
    )

    svc._provider_plans.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_upstream_plan_quota_not_found_raises() -> None:
    """配额不存在（已被删 / 越权 plan）应报 NotFound。"""
    svc = _writes()

    svc._provider_plans.get = AsyncMock(return_value=MagicMock(credential_id=uuid.uuid4()))  # type: ignore[method-assign]
    svc._assert_upstream_credential_writable = AsyncMock(return_value=uuid.uuid4())  # type: ignore[method-assign]
    svc._provider_plans.delete_quota = AsyncMock(return_value=False)  # type: ignore[method-assign]

    with pytest.raises(NotFoundError):
        await svc.delete_plan_quota(
            layer="upstream",
            plan_id=uuid.uuid4(),
            quota_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            actor_user_id=uuid.uuid4(),
            is_platform_admin=False,
            is_team_admin=True,
        )


@pytest.mark.asyncio
async def test_delete_downstream_plan_quota_self_service_denied() -> None:
    """成员自助不可删下游（vkey/apikey）配额。"""
    svc = _writes()

    with pytest.raises(PermissionDeniedError):
        await svc.delete_plan_quota(
            layer="downstream",
            plan_id=uuid.uuid4(),
            quota_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            actor_user_id=uuid.uuid4(),
            is_platform_admin=False,
            is_team_admin=False,
            member_self_service=True,
        )


@pytest.mark.asyncio
async def test_delete_downstream_plan_quota_removes_empty_plan() -> None:
    """删除最后一条下游配额后连带删空套餐。"""
    svc = _writes()
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()

    svc._assert_entitlement_plan_in_team = AsyncMock(return_value=MagicMock())  # type: ignore[method-assign]
    svc._entitlement_plans.delete_quota = AsyncMock(return_value=True)  # type: ignore[method-assign]
    svc._entitlement_plans.list_quotas = AsyncMock(return_value=[])  # type: ignore[method-assign]
    svc._entitlement_plans.delete = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await svc.delete_plan_quota(
        layer="downstream",
        plan_id=plan_id,
        quota_id=quota_id,
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        is_platform_admin=True,
        is_team_admin=False,
    )

    svc._entitlement_plans.delete_quota.assert_awaited_once_with(plan_id, quota_id)
    svc._entitlement_plans.delete.assert_awaited_once_with(plan_id)
    assert svc._invalidate_quota_rule_list_cache.await_args.kwargs["upstream_changed"] is False
