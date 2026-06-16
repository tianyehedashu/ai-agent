"""QuotaPlanUsageBucketRepository 单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.domain.quota_plan import PROVIDER_NS
from domains.gateway.infrastructure.repositories.quota_plan_usage_bucket_repository import (
    QuotaPlanUsageBucketRepository,
)


@pytest.mark.asyncio
async def test_increment_bucket_does_not_commit() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    repo = QuotaPlanUsageBucketRepository(session)
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    window_start = datetime(2026, 6, 20, tzinfo=UTC)

    await repo.increment_bucket(
        PROVIDER_NS,
        plan_id,
        quota_id,
        window_start,
        delta_tokens=10,
        delta_requests=1,
        delta_cost_usd=Decimal("0.1"),
    )

    session.execute.assert_awaited_once()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_stale_updated_before_returns_rowcount() -> None:
    session = MagicMock()
    result = MagicMock()
    result.rowcount = 3
    session.execute = AsyncMock(return_value=result)
    repo = QuotaPlanUsageBucketRepository(session)

    deleted = await repo.delete_stale_updated_before(datetime(2026, 1, 1, tzinfo=UTC))

    assert deleted == 3
    session.execute.assert_awaited_once()
