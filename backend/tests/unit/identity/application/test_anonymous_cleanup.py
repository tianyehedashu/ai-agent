"""anonymous_cleanup 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from domains.identity.application.anonymous_cleanup import cleanup_orphan_anonymous_tenants
from domains.identity.domain.orphan_tenant_tables import ORPHAN_TENANT_CLEANUP_TABLES


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cleanup_orphan_executes_delete_per_table_in_reverse_order() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 2
    session.execute = AsyncMock(return_value=result)

    total = await cleanup_orphan_anonymous_tenants(session, retention_days=30)

    assert total == 2 * len(ORPHAN_TENANT_CLEANUP_TABLES)
    assert session.execute.await_count == len(ORPHAN_TENANT_CLEANUP_TABLES)
    session.flush.assert_awaited_once()

    first_sql = str(session.execute.await_args_list[0].args[0])
    last_sql = str(session.execute.await_args_list[-1].args[0])
    assert ORPHAN_TENANT_CLEANUP_TABLES[-1] in first_sql
    assert ORPHAN_TENANT_CLEANUP_TABLES[0] in last_sql

    cutoff = session.execute.await_args_list[0].args[1]["cutoff"]
    assert cutoff < datetime.now(UTC)
    assert cutoff > datetime.now(UTC) - timedelta(days=31)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cleanup_orphan_skips_flush_when_nothing_deleted() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 0
    session.execute = AsyncMock(return_value=result)

    total = await cleanup_orphan_anonymous_tenants(session, retention_days=7)

    assert total == 0
    session.flush.assert_not_awaited()
