"""Gateway reload_litellm_router 事务行为回归。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management.write_base import (
    GatewayManagementWriteBaseMixin,
)


class _WritesUnderTest(GatewayManagementWriteBaseMixin):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)


@pytest.mark.asyncio
async def test_reload_litellm_router_commits_writes_before_reload(db_session: AsyncSession) -> None:
    writes = _WritesUnderTest(db_session)
    db_session.sync_session.info["_ai_agent_has_writes"] = True
    call_order: list[str] = []

    async def _commit(session: AsyncSession) -> bool:
        call_order.append("commit")
        return True

    async def _reload(session: AsyncSession) -> object:
        call_order.append("reload")
        return object()

    with (
        patch(
            "libs.db.database.commit_pending_writes",
            side_effect=_commit,
        ),
        patch(
            "domains.gateway.infrastructure.litellm.router_singleton.reload_router",
            side_effect=_reload,
        ),
    ):
        await writes.reload_litellm_router()

    assert call_order == ["commit", "reload"]
