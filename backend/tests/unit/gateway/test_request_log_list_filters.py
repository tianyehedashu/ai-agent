"""RequestLogRepository list_by_axis 与 _list_filter_clauses 单测。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.infrastructure.repositories.request_log_repository import (
    RequestLogRepository,
)


@pytest.mark.asyncio
async def test_list_by_axis_passes_user_id_and_model_to_clauses() -> None:
    """list_by_axis 将 user_id 与 model 参数正确传递给 _list_filter_clauses。"""
    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    row = SimpleNamespace(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        status="success",
        user_id=uuid.uuid4(),
    )
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [row]
    session.execute = AsyncMock(side_effect=[count_result, list_result])

    repo = RequestLogRepository(session)
    uid = uuid.uuid4()
    now = datetime.now(UTC)
    items, total = await repo.list_by_axis(
        UsageAxis.workspace(uuid.uuid4()),
        start=now - timedelta(days=1),
        end=now,
        user_id=uid,
        model="gpt-4",
        page=1,
        page_size=20,
    )

    assert total == 1
    assert len(items) == 1
    # 验证执行了 2 次查询（count + list）
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_list_by_axis_with_model_none_ignores_model_filter() -> None:
    """model 为 None 时不应附加 model 相关 OR 子句。"""
    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[count_result, list_result])

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    items, total = await repo.list_by_axis(
        UsageAxis.workspace(uuid.uuid4()),
        start=now - timedelta(days=1),
        end=now,
        model=None,
        page=1,
        page_size=20,
    )

    assert total == 0
    assert items == []


@pytest.mark.asyncio
async def test_list_by_axis_uses_list_filter_clauses_for_all_filters() -> None:
    """list_by_axis 通过 _list_filter_clauses 统一处理所有筛选条件。"""
    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[count_result, list_result])

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    await repo.list_by_axis(
        UsageAxis.workspace(uuid.uuid4()),
        start=now - timedelta(days=1),
        end=now,
        status="success",
        capability="chat",
        vkey_id=uuid.uuid4(),
        credential_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        model="gpt-4",
        page=1,
        page_size=20,
    )

    # 验证执行了 2 次查询
    assert session.execute.await_count == 2


def test_list_filter_clauses_builds_expected_clauses() -> None:
    """_list_filter_clauses 根据传入参数构建正确的筛选子句。"""
    repo = RequestLogRepository.__new__(RequestLogRepository)
    clauses = repo._list_filter_clauses(
        status="success",
        capability="chat",
        user_id=uuid.uuid4(),
        model="gpt-4",
    )
    assert len(clauses) == 4


def test_list_filter_clauses_returns_empty_when_no_filters() -> None:
    """无筛选参数时返回空列表。"""
    repo = RequestLogRepository.__new__(RequestLogRepository)
    clauses = repo._list_filter_clauses()
    assert clauses == []


@pytest.mark.asyncio
async def test_aggregate_summary_by_axis_passes_filter_clauses() -> None:
    """aggregate_summary_by_axis 正确传递筛选参数到 _list_filter_clauses。"""
    session = AsyncMock()
    row = SimpleNamespace(
        total=5,
        input_tokens=10,
        output_tokens=20,
        cost_usd=Decimal("0.05"),
        success=4,
        failure=1,
        avg_latency=100.0,
        avg_ttfb=42.0,
    )
    result = MagicMock()
    result.one.return_value = row
    session.execute = AsyncMock(return_value=result)

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    summary = await repo.aggregate_summary_by_axis(
        UsageAxis.workspace(uuid.uuid4()),
        now - timedelta(days=1),
        now,
        status="failed",
        capability="chat",
        user_id=uuid.uuid4(),
        model="gpt-4",
    )

    assert summary["total"] == 5
    assert summary["success"] == 4
    assert summary["failure"] == 1


@pytest.mark.asyncio
async def test_aggregate_by_client_type_passes_filter_clauses() -> None:
    """aggregate_by_client_type 正确传递筛选参数到 _list_filter_clauses。"""
    session = AsyncMock()
    row = SimpleNamespace(
        client_type="web",
        requests=3,
        cost_usd=Decimal("0.03"),
    )
    result = MagicMock()
    result.all.return_value = [row]
    session.execute = AsyncMock(return_value=result)

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    out = await repo.aggregate_by_client_type(
        UsageAxis.workspace(uuid.uuid4()),
        now - timedelta(days=1),
        now,
        status="success",
        user_id=uuid.uuid4(),
    )

    assert len(out) == 1
    assert out[0]["client_type"] == "web"
    assert out[0]["requests"] == 3
