"""GatewayModel / SystemGatewayModel → HTTP 响应映射。"""

from __future__ import annotations

import pytest

from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.presentation.gateway_model_response import build_gateway_model_response


@pytest.mark.asyncio
async def test_build_gateway_model_response_registry_kind(db_session) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    repo = GatewayModelRepository(db_session)
    system_rows = await repo.list_system(only_enabled=True)
    if not system_rows:
        pytest.skip("catalog sync produced no system models")
    resp = build_gateway_model_response(system_rows[0])
    assert resp.registry_kind == "system"
    assert resp.tenant_id is None
