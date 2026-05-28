"""managed_team_virtual_key_reads 单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.management.managed_team_virtual_key_reads import (
    list_managed_team_virtual_keys_for_actor,
)
from libs.api.pagination import PageParams


@dataclass(frozen=True)
class _Membership:
    team_id: uuid.UUID
    kind: str
    role: str


def _vkey_row(
    key_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    created_by_user_id: uuid.UUID,
    name: str = "test-key",
) -> MagicMock:
    row = MagicMock()
    row.id = key_id
    row.tenant_id = tenant_id
    row.team_id = tenant_id
    row.created_by_user_id = created_by_user_id
    row.is_system = False
    row.is_active = True
    row.name = name
    row.description = None
    row.key_id = "sk-gw-test"
    row.allowed_models = []
    row.allowed_capabilities = []
    row.rpm_limit = None
    row.tpm_limit = None
    row.store_full_messages = False
    row.guardrail_enabled = False
    row.expires_at = None
    row.last_used_at = None
    row.usage_count = 0
    row.created_at = MagicMock()
    row.masked_key_display = "sk-gw-***test"
    return row


@pytest.mark.asyncio
async def test_list_managed_team_keys_filters_by_actor_and_paginates() -> None:
    user_id = uuid.uuid4()
    personal_id = uuid.uuid4()
    shared_id = uuid.uuid4()
    own_key_id = uuid.uuid4()

    session = MagicMock()
    team_listing = MagicMock()
    team_listing.list_gateway_team_memberships = AsyncMock(
        return_value=[
            _Membership(team_id=personal_id, kind="personal", role="owner"),
            _Membership(team_id=shared_id, kind="shared", role="admin"),
        ]
    )

    own_key = _vkey_row(own_key_id, personal_id, created_by_user_id=user_id, name="mine")

    vkey_repo = MagicMock()
    vkey_repo.count_non_system_active_for_tenants = AsyncMock(return_value=1)
    vkey_repo.list_non_system_active_for_tenants = AsyncMock(return_value=[own_key])
    vkey_repo.list_distinct_tenant_ids_with_non_system_active_keys = AsyncMock(
        return_value=[personal_id]
    )

    with patch(
        "domains.gateway.application.management.managed_team_virtual_key_reads.VirtualKeyRepository",
        return_value=vkey_repo,
    ), patch(
        "domains.gateway.application.management.managed_team_virtual_key_reads.virtual_key_from_orm",
        side_effect=lambda row: MagicMock(
            id=row.id,
            tenant_id=row.tenant_id,
            team_id=row.tenant_id,
            name=row.name,
        ),
    ):
        result = await list_managed_team_virtual_keys_for_actor(
            session,
            user_id=user_id,
            is_platform_admin=False,
            page_params=PageParams(page=1, page_size=20),
            team_listing=team_listing,
        )

    assert result.queried_team_count == 2
    assert result.queried_personal_team_count == 1
    assert result.queried_shared_team_count == 1
    assert result.total == 1
    assert [row.id for row in result.page_items] == [own_key_id]
    assert result.tenant_ids_with_keys == (personal_id,)
    vkey_repo.count_non_system_active_for_tenants.assert_awaited_once_with(
        [personal_id, shared_id],
        created_by_user_id=user_id,
    )
    vkey_repo.list_non_system_active_for_tenants.assert_awaited_once_with(
        [personal_id, shared_id],
        created_by_user_id=user_id,
        offset=0,
        limit=20,
    )
