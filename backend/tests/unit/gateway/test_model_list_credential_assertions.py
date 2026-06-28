"""model_list_credential_assertions 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.catalog.model_list_credential_assertions import (
    assert_managed_team_model_list_credential_filter,
    assert_team_model_list_credential_filter,
)
from domains.gateway.domain.errors import CredentialNotFoundError


@pytest.mark.asyncio
async def test_managed_team_filter_delegates_to_access_and_filterable() -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    session = MagicMock()
    row = MagicMock()
    row.tenant_id = tenant_id

    reads = MagicMock()
    reads.access.assert_credential_in_managed_tenants = AsyncMock(return_value=row)
    filterable = AsyncMock()

    with patch(
        "domains.gateway.application.management.reads.GatewayManagementReadService",
        return_value=reads,
    ), patch(
        "domains.gateway.application.catalog.model_list_credential_assertions.assert_team_credential_filterable_for_model_list",
        filterable,
    ):
        await assert_managed_team_model_list_credential_filter(
            session,
            credential_id,
            allowed_tenant_ids=[tenant_id],
            actor_user_id=actor_user_id,
            is_platform_admin=False,
        )

    reads.access.assert_credential_in_managed_tenants.assert_awaited_once_with(
        credential_id,
        allowed_tenant_ids=[tenant_id],
    )
    filterable.assert_awaited_once_with(
        session,
        row,
        credential_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        is_platform_admin=False,
    )


@pytest.mark.asyncio
async def test_managed_team_filter_skips_when_credential_id_none() -> None:
    session = MagicMock()
    reads = MagicMock()
    reads.access.assert_credential_in_managed_tenants = AsyncMock()

    with patch(
        "domains.gateway.application.management.reads.GatewayManagementReadService",
        return_value=reads,
    ):
        await assert_managed_team_model_list_credential_filter(
            session,
            None,
            allowed_tenant_ids=[uuid.uuid4()],
            actor_user_id=uuid.uuid4(),
            is_platform_admin=False,
        )

    reads.access.assert_credential_in_managed_tenants.assert_not_awaited()


@pytest.mark.asyncio
async def test_managed_team_filter_propagates_not_found() -> None:
    credential_id = uuid.uuid4()
    reads = MagicMock()
    reads.access.assert_credential_in_managed_tenants = AsyncMock(
        side_effect=CredentialNotFoundError(str(credential_id))
    )

    with patch(
        "domains.gateway.application.management.reads.GatewayManagementReadService",
        return_value=reads,
    ):
        with pytest.raises(CredentialNotFoundError):
            await assert_managed_team_model_list_credential_filter(
                MagicMock(),
                credential_id,
                allowed_tenant_ids=[uuid.uuid4()],
                actor_user_id=uuid.uuid4(),
                is_platform_admin=False,
            )


@pytest.mark.asyncio
async def test_team_filter_delegates_to_access_and_filterable() -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    session = MagicMock()
    row = MagicMock()

    reads = MagicMock()
    reads.access.assert_credential_in_team = AsyncMock(return_value=row)
    filterable = AsyncMock()

    with patch(
        "domains.gateway.application.catalog.model_list_credential_assertions.assert_team_credential_filterable_for_model_list",
        filterable,
    ):
        await assert_team_model_list_credential_filter(
            session,
            reads,
            credential_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            is_platform_admin=False,
        )

    reads.access.assert_credential_in_team.assert_awaited_once_with(
        credential_id,
        tenant_id=tenant_id,
        is_platform_admin=False,
    )
    filterable.assert_awaited_once_with(
        session,
        row,
        credential_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        is_platform_admin=False,
    )
