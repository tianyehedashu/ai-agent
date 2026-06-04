"""Gateway metrics rollup 仓储单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.infrastructure.repositories.metrics_rollup_repository import (
    GatewayMetricsRollupRepository,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rollup_window_empty_result_skips_upsert_and_commit() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    repo = GatewayMetricsRollupRepository(session)
    since = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
    until = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)

    count = await repo.rollup_window(since, until)

    assert count == 0
    session.commit.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rollup_window_batches_upsert_in_single_execute() -> None:
    session = AsyncMock()
    bucket_at = datetime(2026, 5, 27, 11, 0, tzinfo=UTC)
    tenant_id = uuid.uuid4()
    row = SimpleNamespace(
        bucket_at=bucket_at,
        tenant_id=tenant_id,
        user_id=None,
        vkey_id=None,
        credential_id=None,
        entitlement_plan_id=None,
        provider_plan_id=None,
        provider="openai",
        real_model="gpt-4",
        capability="chat",
        requests=3,
        success_count=2,
        error_count=1,
        input_tokens=10,
        output_tokens=20,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.001"),
        total_latency_ms=300,
        cache_hit_count=0,
    )
    session.execute = AsyncMock(
        side_effect=[
            MagicMock(all=MagicMock(return_value=[row])),
            MagicMock(),
        ]
    )

    repo = GatewayMetricsRollupRepository(session)
    since = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
    until = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)

    count = await repo.rollup_window(since, until)

    assert count == 1
    assert session.execute.await_count == 2
    session.commit.assert_awaited_once()

    upsert_stmt = session.execute.await_args_list[1].args[0]
    compiled = str(upsert_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "INSERT INTO gateway_metrics_hourly" in compiled
    assert "ON CONFLICT" in compiled.upper()
