"""model_list_credential_assertions 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.model_list_credential_assertions import (
    assert_managed_team_model_list_credential_filter,
)
from domains.gateway.domain.errors import CredentialNotFoundError


@pytest.mark.asyncio
async def test_managed_team_filter_delegates_to_reads() -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    session = MagicMock()

    reads = MagicMock()
    reads.assert_credential_in_managed_tenants = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "domains.gateway.application.management.reads.GatewayManagementReadService",
            lambda _session: reads,
        )
        await assert_managed_team_model_list_credential_filter(
            session,
            credential_id,
            allowed_tenant_ids=[tenant_id],
        )

    reads.assert_credential_in_managed_tenants.assert_awaited_once_with(
        credential_id,
        allowed_tenant_ids=[tenant_id],
    )


@pytest.mark.asyncio
async def test_managed_team_filter_skips_when_credential_id_none() -> None:
    session = MagicMock()
    reads = MagicMock()
    reads.assert_credential_in_managed_tenants = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "domains.gateway.application.management.reads.GatewayManagementReadService",
            lambda _session: reads,
        )
        await assert_managed_team_model_list_credential_filter(
            session,
            None,
            allowed_tenant_ids=[uuid.uuid4()],
        )

    reads.assert_credential_in_managed_tenants.assert_not_awaited()


@pytest.mark.asyncio
async def test_managed_team_filter_propagates_not_found() -> None:
    credential_id = uuid.uuid4()
    reads = MagicMock()
    reads.assert_credential_in_managed_tenants = AsyncMock(
        side_effect=CredentialNotFoundError(str(credential_id))
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "domains.gateway.application.management.reads.GatewayManagementReadService",
            lambda _session: reads,
        )
        with pytest.raises(CredentialNotFoundError):
            await assert_managed_team_model_list_credential_filter(
                MagicMock(),
                credential_id,
                allowed_tenant_ids=[uuid.uuid4()],
            )
