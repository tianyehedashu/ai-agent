"""RequestLogRepository list_by_axis probe 分页单测。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.domain.usage.usage_axis import UsageAxis
from domains.gateway.infrastructure.repositories.request_log_repository import (
    RequestLogRepository,
)


@pytest.mark.asyncio
async def test_list_by_axis_user_axis_skips_count_uses_probe_limit() -> None:
    session = AsyncMock()
    rows = [
        SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(UTC)),
        SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(UTC)),
    ]
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=list_result)

    repo = RequestLogRepository(session)
    uid = uuid.uuid4()
    now = datetime.now(UTC)
    page = await repo.list_by_axis(
        UsageAxis.user(uid),
        start=now - timedelta(days=1),
        end=now,
        page=1,
        page_size=20,
    )

    assert len(page.items) == 2
    assert page.has_next is False
    assert session.execute.await_count == 1
    stmt = session.execute.await_args_list[0].args[0]
    assert "LIMIT" in str(stmt).upper()


@pytest.mark.asyncio
async def test_list_by_axis_probe_detects_has_next() -> None:
    session = AsyncMock()
    page_size = 2
    rows = [SimpleNamespace(id=uuid.uuid4()) for _ in range(page_size + 1)]
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=list_result)

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    page = await repo.list_by_axis(
        UsageAxis.workspace(uuid.uuid4()),
        start=now - timedelta(days=1),
        end=now,
        page=1,
        page_size=page_size,
    )

    assert len(page.items) == page_size
    assert page.has_next is True


@pytest.mark.asyncio
async def test_count_usage_requests_by_axis_user_axis_still_uses_split_count() -> None:
    from domains.gateway.domain.usage.usage_read_model import UsageStatisticsFilters

    session = AsyncMock()
    count_a = MagicMock()
    count_a.scalar_one.return_value = 4
    count_b = MagicMock()
    count_b.scalar_one.return_value = 1
    session.execute = AsyncMock(side_effect=[count_a, count_b])

    repo = RequestLogRepository(session)
    uid = uuid.uuid4()
    now = datetime.now(UTC)
    total = await repo.count_usage_requests_by_axis(
        UsageAxis.user(uid),
        now - timedelta(days=7),
        now,
        filters=UsageStatisticsFilters(),
    )

    assert total == 5
    assert session.execute.await_count == 2
