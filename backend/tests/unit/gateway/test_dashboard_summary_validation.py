"""Dashboard /summary 路由参数校验单测。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.presentation.routers.dashboard import dashboard_summary
from domains.tenancy.domain.management_context import ManagementTeamContext
from libs.exceptions import ValidationError


@pytest.fixture
def fake_team():
    return ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="shared",
        team_role="admin",
        user_id=uuid.uuid4(),
        is_platform_admin=True,
    )


@pytest.fixture
def fake_reads():
    reads = MagicMock()
    reads.aggregate_request_log_summary = AsyncMock(
        return_value={
            "total": 10,
            "input_tokens": 100,
            "output_tokens": 200,
            "cost_usd": Decimal("0.1"),
            "success": 8,
            "failure": 2,
            "avg_latency_ms": 150.0,
            "avg_ttfb_ms": 42.0,
            "by_client_type": [],
        }
    )
    return reads


@pytest.mark.asyncio
async def test_dashboard_summary_rejects_inverted_date_range(fake_team, fake_reads) -> None:
    """start > end 时应返回 422 错误。"""
    end = datetime.now(UTC)
    start = end + timedelta(days=1)
    with pytest.raises(ValidationError) as exc_info:
        await dashboard_summary(
            team=fake_team,
            reads=fake_reads,
            days=7,
            start=start,
            end=end,
        )
    assert "start must be before or equal to end" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dashboard_summary_accepts_equal_dates(fake_team, fake_reads) -> None:
    """start == end 时应允许通过。"""
    now = datetime.now(UTC)
    result = await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        start=now,
        end=now,
        status_filter=None,
        capability=None,
        model=None,
    )
    assert result.total_requests == 10


@pytest.mark.asyncio
async def test_dashboard_summary_strips_whitespace_from_status(fake_team, fake_reads) -> None:
    """status_filter 前后空格应被 strip。"""
    await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        status_filter="  success  ",
        capability=None,
        model=None,
    )
    call_kwargs = fake_reads.aggregate_request_log_summary.await_args.kwargs
    assert call_kwargs["status_filter"] == "success"


@pytest.mark.asyncio
async def test_dashboard_summary_strips_whitespace_from_capability(fake_team, fake_reads) -> None:
    """capability 前后空格应被 strip。"""
    await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        capability="  chat  ",
        status_filter=None,
        model=None,
    )
    call_kwargs = fake_reads.aggregate_request_log_summary.await_args.kwargs
    assert call_kwargs["capability"] == "chat"


@pytest.mark.asyncio
async def test_dashboard_summary_strips_whitespace_from_model(fake_team, fake_reads) -> None:
    """model 前后空格应被 strip。"""
    await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        model="  gpt-4  ",
        status_filter=None,
        capability=None,
    )
    call_kwargs = fake_reads.aggregate_request_log_summary.await_args.kwargs
    assert call_kwargs["model"] == "gpt-4"


@pytest.mark.asyncio
async def test_dashboard_summary_passes_all_filter_params(fake_team, fake_reads) -> None:
    """所有筛选参数应正确透传给 aggregate_request_log_summary。"""
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    vid = uuid.uuid4()
    start = datetime.now(UTC) - timedelta(days=1)
    end = datetime.now(UTC)
    await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        start=start,
        end=end,
        status_filter="failed",
        capability="chat",
        vkey_id=vid,
        credential_id=cid,
        user_id=uid,
        model="gpt-4",
    )
    call_kwargs = fake_reads.aggregate_request_log_summary.await_args.kwargs
    assert call_kwargs["status_filter"] == "failed"
    assert call_kwargs["capability"] == "chat"
    assert call_kwargs["vkey_id"] == vid
    assert call_kwargs["credential_id"] == cid
    assert call_kwargs["user_id"] == uid
    assert call_kwargs["model"] == "gpt-4"
