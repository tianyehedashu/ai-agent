"""GatewayManagementReadService 模型路由用量聚合单测。"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.presentation.schemas.common import PlatformCredentialStatItem
from domains.tenancy.domain.management_context import ManagementTeamContext


@pytest.mark.asyncio
async def test_aggregate_gateway_model_route_usage_merges_workspace_and_user() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="admin",
        user_id=user_id,
        is_platform_admin=False,
    )
    m1 = SimpleNamespace(id=uuid.uuid4(), name="alpha-model")
    m2 = SimpleNamespace(id=uuid.uuid4(), name="beta-model")
    route_ws = {
        "alpha-model": {
            "requests": 1,
            "input_tokens": 4,
            "output_tokens": 1,
            "cost_usd": Decimal("0.004"),
        },
        "beta-model": {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": Decimal("0"),
        },
    }
    route_user = {
        "alpha-model": {
            "requests": 0,
            "input_tokens": 1,
            "output_tokens": 0,
            "cost_usd": Decimal("0.001"),
        },
        "beta-model": {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": Decimal("0"),
        },
    }
    dep_ws = {
        m1.id: {
            "requests": 1,
            "input_tokens": 6,
            "output_tokens": 2,
            "cost_usd": Decimal("0.006"),
        },
        m2.id: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": Decimal("0"),
        },
    }
    dep_user = {
        m1.id: {
            "requests": 1,
            "input_tokens": 4,
            "output_tokens": 1,
            "cost_usd": Decimal("0.004"),
        },
        m2.id: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": Decimal("0"),
        },
    }

    async def _route_axis(axis, _names, _s, _e):
        return route_ws if axis.is_workspace() else route_user

    async def _dep_axis(axis, _ids, _s, _e):
        return dep_ws if axis.is_workspace() else dep_user

    svc._logs.aggregate_by_route_names_by_axis = AsyncMock(side_effect=_route_axis)
    svc._logs.aggregate_by_deployment_ids_by_axis = AsyncMock(side_effect=_dep_axis)

    with patch(
        "domains.gateway.application.management.usage_log_reads.list_merged_models_for_tenant",
        new=AsyncMock(return_value=[m1, m2]),
    ):
        raw = await svc.aggregate_gateway_model_route_usage(ctx, days=7, provider=None)
    assert raw["items"][0]["route_name"] == "alpha-model"
    assert raw["items"][0]["workspace"]["requests"] == 2
    assert raw["items"][0]["user"]["requests"] == 1
    assert raw["items"][1]["route_name"] == "beta-model"


@pytest.mark.asyncio
async def test_aggregate_gateway_model_route_usage_no_models_returns_empty_items() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    ctx = ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="shared",
        team_role="admin",
        user_id=uuid.uuid4(),
        is_platform_admin=False,
    )
    svc._logs.aggregate_by_route_names_by_axis = AsyncMock()
    svc._logs.aggregate_by_deployment_ids_by_axis = AsyncMock()

    with patch(
        "domains.gateway.application.management.usage_log_reads.list_merged_models_for_tenant",
        new=AsyncMock(return_value=[]),
    ):
        raw = await svc.aggregate_gateway_model_route_usage(ctx, days=7, provider=None)

    assert raw["items"] == []
    svc._logs.aggregate_by_route_names_by_axis.assert_not_called()
    svc._logs.aggregate_by_deployment_ids_by_axis.assert_not_called()


@pytest.mark.asyncio
async def test_list_platform_credential_stats_unions_usage_only_and_count_only_credentials() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    usage_only = uuid.uuid4()
    count_only = uuid.uuid4()
    svc._logs.aggregate_by_credential_global = AsyncMock(
        return_value={
            usage_only: {
                "requests": 1,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": Decimal("0"),
                "success": 1,
                "failure": 0,
            }
        }
    )
    svc._models.count_models_grouped_by_credential = AsyncMock(return_value=[(count_only, 3)])
    svc._models.count_system_models_grouped_by_credential = AsyncMock(return_value=[])
    cred_usage = SimpleNamespace(
        id=usage_only,
        provider="openai",
        name="live",
        tenant_id=uuid.uuid4(),
        scope=None,
        scope_id=None,
        is_active=True,
    )
    cred_count = SimpleNamespace(
        id=count_only,
        provider="anthropic",
        name="orphan",
        tenant_id=uuid.uuid4(),
        scope=None,
        scope_id=None,
        is_active=True,
    )
    svc._creds.list_by_ids = AsyncMock(return_value=[cred_usage, cred_count])

    rows = await svc.list_platform_credential_stats(days=7)
    by_id = {r["credential_id"]: r for r in rows}

    assert set(by_id) == {usage_only, count_only}
    assert by_id[usage_only]["gateway_model_count"] == 0
    assert by_id[usage_only]["requests"] == 1
    assert by_id[count_only]["gateway_model_count"] == 3
    assert by_id[count_only]["requests"] == 0
    assert by_id[usage_only]["scope"] == "team"
    assert by_id[count_only]["scope"] == "team"


@pytest.mark.asyncio
async def test_list_platform_credential_stats_system_credential_scope() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    sys_cid = uuid.uuid4()
    svc._logs.aggregate_by_credential_global = AsyncMock(
        return_value={
            sys_cid: {
                "requests": 2,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": Decimal("0"),
                "success": 2,
                "failure": 0,
            }
        }
    )
    svc._models.count_models_grouped_by_credential = AsyncMock(return_value=[])
    svc._models.count_system_models_grouped_by_credential = AsyncMock(return_value=[])
    svc._creds.list_by_ids = AsyncMock(return_value=[])
    sys_cred = SimpleNamespace(
        id=sys_cid,
        provider="openai",
        name="platform-key",
        is_active=True,
    )
    svc._system_creds.list_by_ids = AsyncMock(return_value=[sys_cred])
    rows = await svc.list_platform_credential_stats(days=7)

    assert len(rows) == 1
    assert rows[0]["scope"] == "system"
    assert rows[0]["name"] == "platform-key"
    PlatformCredentialStatItem.model_validate(rows[0])


@pytest.mark.asyncio
async def test_list_platform_credential_stats_merges_tenant_and_system_model_counts() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    cid = uuid.uuid4()
    svc._logs.aggregate_by_credential_global = AsyncMock(return_value={})
    svc._models.count_models_grouped_by_credential = AsyncMock(return_value=[(cid, 2)])
    svc._models.count_system_models_grouped_by_credential = AsyncMock(return_value=[(cid, 5)])
    svc._creds.list_by_ids = AsyncMock(return_value=[])
    sys_cred = SimpleNamespace(
        id=cid,
        provider="openai",
        name="platform",
        is_active=True,
    )
    svc._system_creds.list_by_ids = AsyncMock(return_value=[sys_cred])

    rows = await svc.list_platform_credential_stats(days=7)
    assert len(rows) == 1
    assert rows[0]["gateway_model_count"] == 7
    assert rows[0]["scope"] == "system"


@pytest.mark.asyncio
async def test_list_platform_credential_stats_merges_usage_and_counts() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    cid = uuid.uuid4()
    svc._logs.aggregate_by_credential_global = AsyncMock(
        return_value={
            cid: {
                "requests": 3,
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": Decimal("0.02"),
                "success": 2,
                "failure": 1,
            }
        }
    )
    svc._models.count_models_grouped_by_credential = AsyncMock(return_value=[(cid, 2)])
    svc._models.count_system_models_grouped_by_credential = AsyncMock(return_value=[])
    cred = SimpleNamespace(
        id=cid,
        provider="openai",
        name="k1",
        tenant_id=uuid.uuid4(),
        scope=None,
        scope_id=None,
        is_active=True,
    )
    svc._creds.list_by_ids = AsyncMock(return_value=[cred])

    rows = await svc.list_platform_credential_stats(days=1)
    assert len(rows) == 1
    assert rows[0]["credential_id"] == cid
    assert rows[0]["gateway_model_count"] == 2
    assert rows[0]["requests"] == 3
    assert rows[0]["scope"] == "team"
