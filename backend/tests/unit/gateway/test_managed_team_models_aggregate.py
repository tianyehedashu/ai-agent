"""managed_team_model_reads 单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.catalog.management.managed_team_model_reads import (
    list_managed_team_models_for_actor,
)
from domains.gateway.application.catalog.model_list_pipeline import (
    ModelListPageResult,
    ModelListQuery,
)
from domains.gateway.domain.catalog.model_list_policy import ModelListConnectivityFilter
from libs.api.pagination import PageParams


@dataclass(frozen=True)
class _Membership:
    team_id: uuid.UUID
    kind: str
    role: str


@pytest.mark.asyncio
async def test_list_managed_team_models_excludes_personal_and_passes_filters() -> None:
    user_id = uuid.uuid4()
    shared_id = uuid.uuid4()
    personal_id = uuid.uuid4()
    session = MagicMock()
    team_listing = MagicMock()
    team_listing.list_gateway_team_memberships = AsyncMock(
        return_value=[
            _Membership(team_id=personal_id, kind="personal", role="owner"),
            _Membership(team_id=shared_id, kind="shared", role="admin"),
        ]
    )
    query = ModelListQuery(
        page_params=PageParams(page=1, page_size=20),
        q="gpt",
        connectivity=ModelListConnectivityFilter.SUCCESS,
    )
    page = ModelListPageResult(
        items=[],
        total=0,
        page=1,
        page_size=20,
        connectivity_summary={"total": 0, "success": 0, "failed": 0, "unknown": 0},
    )

    with (
        patch(
            "domains.gateway.application.catalog.management.managed_team_model_reads.ModelListReadRepository"
        ) as repo_cls,
        patch(
            "domains.gateway.application.catalog.management.managed_team_model_reads.readable_team_credential_ids_for_tenants",
            new=AsyncMock(return_value=frozenset()),
        ),
        patch(
            "domains.gateway.application.catalog.management.managed_team_model_reads.list_gateway_models_for_tenants_page",
            new=AsyncMock(return_value=page),
        ) as list_page,
    ):
        repo = repo_cls.return_value
        repo.list_tenant_ids_with_team_registry = AsyncMock(return_value=[shared_id])

        result = await list_managed_team_models_for_actor(
            session,
            user_id=user_id,
            is_platform_admin=False,
            query=query,
            search=None,
            team_listing=team_listing,
        )

    assert result.queried_team_count == 1
    assert result.queried_personal_team_count == 0
    assert result.queried_shared_team_count == 1
    assert result.tenant_ids_with_models == (shared_id,)

    repo.list_tenant_ids_with_team_registry.assert_awaited_once()
    kwargs = repo.list_tenant_ids_with_team_registry.await_args.kwargs
    assert kwargs["q"] == "gpt"
    assert kwargs["connectivity"] == ModelListConnectivityFilter.SUCCESS

    list_page.assert_awaited_once()
    assert list_page.await_args.args[1] == [shared_id]
