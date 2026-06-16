"""Dashboard hybrid 读路径集成测试：对比 hourly + logs 与纯 logs 聚合结果。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.gateway.application.management.usage_metrics_window import compute_hot_cutoff, floor_hour
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.repositories.metrics_rollup_repository import (
    GatewayMetricsRollupRepository,
    RollupUpsertMode,
)
from domains.tenancy.application.team_service import TeamService

_SUMMARY_COMPARE_KEYS = (
    "total_requests",
    "total_input_tokens",
    "total_output_tokens",
    "total_cached_tokens",
    "total_cache_creation_tokens",
    "success_count",
    "failure_count",
    "avg_latency_ms",
    "avg_ttfb_ms",
    "success_rate",
)

_TOTALS_COMPARE_KEYS = (
    "requests",
    "success_count",
    "failure_count",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "cache_creation_tokens",
    "avg_latency_ms",
    "avg_ttfb_ms",
    "cache_hit_count",
)


async def _rollup_logs(
    db_session: AsyncSession,
    since: datetime,
    until: datetime,
) -> int:
    repo = GatewayMetricsRollupRepository(db_session)
    return await repo.rollup_window(since, until, mode=RollupUpsertMode.REPLACE)


def _add_request_log(
    *,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    created_at: datetime,
    credential_id: uuid.UUID,
    route_name: str,
    status: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    ttfb_ms: int,
    cached_tokens: int = 0,
    cache_hit: bool = False,
) -> GatewayRequestLog:
    return GatewayRequestLog(
        tenant_id=team_id,
        user_id=user_id,
        vkey_id=uuid.uuid4(),
        credential_id=credential_id,
        credential_name_snapshot="hybrid-cred",
        route_name=route_name,
        provider="openai",
        capability="chat",
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        cache_hit=cache_hit,
        cost_usd=Decimal("0.0001"),
        latency_ms=latency_ms,
        ttfb_ms=ttfb_ms,
        created_at=created_at,
        request_id=f"req-hybrid-{uuid.uuid4()}",
    )


async def _fetch_summary(
    dev_client: AsyncClient,
    team_id: uuid.UUID,
    auth_headers: dict[str, str],
    *,
    days: int = 7,
) -> dict[str, Any]:
    response = await dev_client.get(
        f"/api/v1/gateway/teams/{team_id}/dashboard/summary",
        params={"days": days},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _fetch_statistics(
    dev_client: AsyncClient,
    team_id: uuid.UUID,
    auth_headers: dict[str, str],
    *,
    days: int = 7,
    group_by: str = "credential",
) -> dict[str, Any]:
    response = await dev_client.get(
        f"/api/v1/gateway/teams/{team_id}/dashboard/statistics",
        params={"days": days, "group_by": group_by, "page": 1, "page_size": 20},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_summary_equal(hybrid: dict[str, Any], logs_only: dict[str, Any]) -> None:
    for key in _SUMMARY_COMPARE_KEYS:
        if key == "success_rate":
            assert hybrid[key] == pytest.approx(logs_only[key], rel=1e-6)
        elif key in {"avg_latency_ms", "avg_ttfb_ms"}:
            assert hybrid[key] == pytest.approx(logs_only[key], rel=1e-3)
        else:
            assert hybrid[key] == logs_only[key], key


def _assert_statistics_equal(hybrid: dict[str, Any], logs_only: dict[str, Any]) -> None:
    hybrid_totals = hybrid["totals"]
    logs_totals = logs_only["totals"]
    for key in _TOTALS_COMPARE_KEYS:
        if key in {"avg_latency_ms", "avg_ttfb_ms"}:
            assert hybrid_totals[key] == pytest.approx(logs_totals[key], rel=1e-3)
        else:
            assert hybrid_totals[key] == logs_totals[key], key

    assert hybrid["total"] == logs_only["total"]
    hybrid_items = sorted(hybrid["items"], key=lambda item: item["group_key"])
    logs_items = sorted(logs_only["items"], key=lambda item: item["group_key"])
    assert len(hybrid_items) == len(logs_items)
    for hybrid_item, logs_item in zip(hybrid_items, logs_items, strict=True):
        assert hybrid_item["group_key"] == logs_item["group_key"]
        assert hybrid_item["requests"] == logs_item["requests"]
        assert hybrid_item["success_count"] == logs_item["success_count"]
        assert hybrid_item["failure_count"] == logs_item["failure_count"]
        assert hybrid_item["input_tokens"] == logs_item["input_tokens"]
        assert hybrid_item["output_tokens"] == logs_item["output_tokens"]
        assert hybrid_item["avg_latency_ms"] == pytest.approx(logs_item["avg_latency_ms"], rel=1e-3)
        assert hybrid_item["avg_ttfb_ms"] == pytest.approx(logs_item["avg_ttfb_ms"], rel=1e-3)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_dashboard_summary_matches_logs_for_cold_window(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史段（热尾之外）写入 hourly 后，hybrid summary 应与纯 logs 一致。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    credential_id = uuid.uuid4()
    cold_at = datetime.now(UTC) - timedelta(days=3)
    cold_at = cold_at.replace(minute=15, second=0, microsecond=0)
    db_session.add_all(
        [
            _add_request_log(
                team_id=team.id,
                user_id=test_user.id,
                created_at=cold_at,
                credential_id=credential_id,
                route_name="cold-model-a",
                status="success",
                input_tokens=100,
                output_tokens=40,
                latency_ms=120,
                ttfb_ms=30,
                cached_tokens=10,
                cache_hit=True,
            ),
            _add_request_log(
                team_id=team.id,
                user_id=test_user.id,
                created_at=cold_at + timedelta(minutes=5),
                credential_id=credential_id,
                route_name="cold-model-a",
                status="failed",
                input_tokens=20,
                output_tokens=0,
                latency_ms=900,
                ttfb_ms=800,
            ),
        ]
    )
    await db_session.flush()

    rollup_since = floor_hour(cold_at) - timedelta(hours=1)
    rollup_until = compute_hot_cutoff(hot_tail_hours=settings.gateway_metrics_hot_tail_hours)
    rolled = await _rollup_logs(db_session, rollup_since, rollup_until)
    assert rolled >= 1

    monkeypatch.setattr(settings, "gateway_metrics_hybrid_read_enabled", True)
    hybrid_summary = await _fetch_summary(dev_client, team.id, auth_headers)

    monkeypatch.setattr(settings, "gateway_metrics_hybrid_read_enabled", False)
    logs_summary = await _fetch_summary(dev_client, team.id, auth_headers)

    _assert_summary_equal(hybrid_summary, logs_summary)
    assert hybrid_summary["total_requests"] == 2
    assert hybrid_summary["success_count"] == 1
    assert hybrid_summary["failure_count"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_dashboard_statistics_matches_logs_for_cold_window(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史段 statistics 在 hybrid 与纯 logs 路径下 totals / items 应一致。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    credential_id = uuid.uuid4()
    cold_at = datetime.now(UTC) - timedelta(days=2, hours=6)
    cold_at = cold_at.replace(minute=30, second=0, microsecond=0)
    db_session.add_all(
        [
            _add_request_log(
                team_id=team.id,
                user_id=test_user.id,
                created_at=cold_at,
                credential_id=credential_id,
                route_name="stats-model",
                status="success",
                input_tokens=50,
                output_tokens=25,
                latency_ms=100,
                ttfb_ms=20,
            ),
            _add_request_log(
                team_id=team.id,
                user_id=test_user.id,
                created_at=cold_at + timedelta(minutes=10),
                credential_id=credential_id,
                route_name="stats-model",
                status="success",
                input_tokens=70,
                output_tokens=35,
                latency_ms=300,
                ttfb_ms=60,
            ),
        ]
    )
    await db_session.flush()

    rollup_since = floor_hour(cold_at) - timedelta(hours=1)
    rollup_until = compute_hot_cutoff(hot_tail_hours=settings.gateway_metrics_hot_tail_hours)
    rolled = await _rollup_logs(db_session, rollup_since, rollup_until)
    assert rolled >= 1

    monkeypatch.setattr(settings, "gateway_metrics_hybrid_read_enabled", True)
    hybrid_stats = await _fetch_statistics(dev_client, team.id, auth_headers)

    monkeypatch.setattr(settings, "gateway_metrics_hybrid_read_enabled", False)
    logs_stats = await _fetch_statistics(dev_client, team.id, auth_headers)

    _assert_statistics_equal(hybrid_stats, logs_stats)
    assert hybrid_stats["totals"]["requests"] == 2
    assert hybrid_stats["totals"]["avg_latency_ms"] == pytest.approx(200)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_dashboard_summary_merges_cold_hourly_and_hot_logs(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """跨热尾边界：冷段读 hourly、热段读 logs，合并后应与纯 logs 一致。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    credential_id = uuid.uuid4()
    hot_cutoff = compute_hot_cutoff(hot_tail_hours=settings.gateway_metrics_hot_tail_hours)
    cold_at = hot_cutoff - timedelta(days=1)
    hot_at = hot_cutoff + timedelta(minutes=30)

    db_session.add_all(
        [
            _add_request_log(
                team_id=team.id,
                user_id=test_user.id,
                created_at=cold_at,
                credential_id=credential_id,
                route_name="cross-model",
                status="success",
                input_tokens=80,
                output_tokens=20,
                latency_ms=100,
                ttfb_ms=25,
            ),
            _add_request_log(
                team_id=team.id,
                user_id=test_user.id,
                created_at=hot_at,
                credential_id=credential_id,
                route_name="cross-model",
                status="success",
                input_tokens=30,
                output_tokens=10,
                latency_ms=200,
                ttfb_ms=50,
            ),
        ]
    )
    await db_session.flush()

    rolled = await _rollup_logs(db_session, floor_hour(cold_at) - timedelta(hours=1), hot_cutoff)
    assert rolled >= 1

    monkeypatch.setattr(settings, "gateway_metrics_hybrid_read_enabled", True)
    hybrid_summary = await _fetch_summary(dev_client, team.id, auth_headers, days=7)

    monkeypatch.setattr(settings, "gateway_metrics_hybrid_read_enabled", False)
    logs_summary = await _fetch_summary(dev_client, team.id, auth_headers, days=7)

    _assert_summary_equal(hybrid_summary, logs_summary)
    assert hybrid_summary["total_requests"] == 2
    assert hybrid_summary["total_input_tokens"] == 110
    assert hybrid_summary["total_output_tokens"] == 30


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_dashboard_summary_status_filter_matches_logs_only(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """带 status 筛选时 summary 应整窗走 logs，与 hybrid 关闭结果一致。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    credential_id = uuid.uuid4()
    cold_at = datetime.now(UTC) - timedelta(days=3)
    cold_at = cold_at.replace(minute=10, second=0, microsecond=0)
    db_session.add_all(
        [
            _add_request_log(
                team_id=team.id,
                user_id=test_user.id,
                created_at=cold_at,
                credential_id=credential_id,
                route_name="status-model",
                status="success",
                input_tokens=10,
                output_tokens=5,
                latency_ms=100,
                ttfb_ms=20,
            ),
            _add_request_log(
                team_id=team.id,
                user_id=test_user.id,
                created_at=cold_at + timedelta(minutes=5),
                credential_id=credential_id,
                route_name="status-model",
                status="failed",
                input_tokens=20,
                output_tokens=0,
                latency_ms=500,
                ttfb_ms=400,
            ),
        ]
    )
    await db_session.flush()

    rollup_since = floor_hour(cold_at) - timedelta(hours=1)
    rollup_until = compute_hot_cutoff(hot_tail_hours=settings.gateway_metrics_hot_tail_hours)
    await _rollup_logs(db_session, rollup_since, rollup_until)

    async def _fetch_failed_summary() -> dict[str, Any]:
        response = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/dashboard/summary",
            params={"days": 7, "status": "failed"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    monkeypatch.setattr(settings, "gateway_metrics_hybrid_read_enabled", True)
    hybrid_failed = await _fetch_failed_summary()
    monkeypatch.setattr(settings, "gateway_metrics_hybrid_read_enabled", False)
    logs_failed = await _fetch_failed_summary()

    assert hybrid_failed["total_requests"] == logs_failed["total_requests"] == 1
    assert hybrid_failed["success_count"] == logs_failed["success_count"] == 0
    assert hybrid_failed["failure_count"] == logs_failed["failure_count"] == 1
