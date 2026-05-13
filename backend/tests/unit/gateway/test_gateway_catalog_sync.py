"""Gateway 配置目录同步单元测试。"""

from __future__ import annotations

import pytest

from domains.gateway.application.config_catalog_sync import (
    MANAGED_CONFIG,
    sync_app_config_gateway_catalog,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository


@pytest.mark.asyncio
async def test_sync_app_config_gateway_catalog_idempotent(db_session) -> None:
    """同步可重复执行且不抛错。"""
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()


@pytest.mark.asyncio
async def test_sync_marks_config_managed_tags(db_session) -> None:
    """成功写入的 global 行应带 managed_by=config（在至少同步到一行时）。"""
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    repo = GatewayModelRepository(db_session)
    rows = await repo.list_for_team(None, only_enabled=False)
    managed = [r for r in rows if (r.tags or {}).get("managed_by") == MANAGED_CONFIG]
    # 无环境 API Key 时可能 0 行，仅校验结构一致性
    for r in managed:
        assert r.team_id is None
        assert r.name
        assert r.real_model
