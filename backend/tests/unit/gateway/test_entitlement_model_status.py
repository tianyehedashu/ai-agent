"""entitlement_model_status 与 guard 列表态单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.entitlement_guard import _status_from_quota_snapshots
from domains.gateway.application.entitlement_model_status import (
    compute_model_callable,
    connectivity_status_from_last_test,
    entitlement_status_by_model_names,
    is_connectivity_requestable,
    resolve_entitlement_scope,
)
from domains.gateway.application.proxy_model_list_reads import build_proxy_models_list
from domains.gateway.domain.quota_plan import PlanQuotaSnapshot, PlanQuotaSpec
from domains.gateway.domain.types import EntitlementListStatus, ModelConnectivityStatus
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    ENTITLEMENT_SCOPE_VKEY,
)


def test_resolve_entitlement_scope_vkey() -> None:
    vid = uuid.uuid4()
    scope, sid = resolve_entitlement_scope(vkey_id=vid)
    assert scope == ENTITLEMENT_SCOPE_VKEY
    assert sid == vid


@pytest.mark.parametrize(
    ("connectivity", "entitlement", "expected"),
    [
        ("failed", "active", False),
        (None, "exhausted", False),
        (None, "expired", False),
        (None, "resetting", True),
        ("success", "active", True),
    ],
)
def test_compute_model_callable(
    connectivity: ModelConnectivityStatus | None,
    entitlement: EntitlementListStatus,
    expected: bool,
) -> None:
    assert (
        compute_model_callable(
            connectivity_status=connectivity,
            entitlement_status=entitlement,
        )
        is expected
    )


def test_connectivity_status_from_last_test() -> None:
    assert connectivity_status_from_last_test("success") == "success"
    assert connectivity_status_from_last_test("failed") == "failed"
    assert connectivity_status_from_last_test(None) is None


@pytest.mark.parametrize(
    ("last_test_status", "expected"),
    [
        ("success", True),
        (None, True),
        ("failed", False),
    ],
)
def test_is_connectivity_requestable(last_test_status: str | None, expected: bool) -> None:
    assert is_connectivity_requestable(last_test_status) is expected


def test_status_from_quota_snapshots_resetting() -> None:
    when = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="5h",
        window_seconds=18_000,
        limit_usd=None,
        limit_tokens=None,
        limit_requests=100,
        reset_strategy="rolling",
    )
    snap = PlanQuotaSnapshot(
        spec=spec,
        used_requests=100,
        exhausted_reason="requests",
        earliest_minute_in_window=int(when.timestamp()) // 60 - 10,
    )
    status = _status_from_quota_snapshots([snap], when=when)
    assert status in ("exhausted", "resetting")


@pytest.mark.asyncio
async def test_build_proxy_models_list_uses_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    row = GatewayModel(
        name="m1",
        capability="chat",
        real_model="p/m1",
        credential_id=uuid.uuid4(),
        provider="p",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    mock_guard = MagicMock()
    mock_guard.status_for_models = AsyncMock(return_value={"m1": "exhausted"})
    mock_build = MagicMock(return_value=mock_guard)
    monkeypatch.setattr(
        "domains.gateway.application.entitlement_guard.build_entitlement_guard_for_session",
        mock_build,
    )
    monkeypatch.setattr(
        "domains.gateway.application.model_credential_enrichment.build_credential_profile_map_for_models",
        AsyncMock(return_value={}),
    )
    session = MagicMock()
    items = await build_proxy_models_list(
        session,
        [row],
        entitlement_scope=ENTITLEMENT_SCOPE_VKEY,
        entitlement_scope_id=uuid.uuid4(),
    )
    assert len(items) == 1
    assert items[0]["gateway"]["entitlement_status"] == "exhausted"
    assert items[0]["gateway"]["callable"] is False
    mock_guard.status_for_models.assert_awaited_once()


@pytest.mark.asyncio
async def test_entitlement_status_by_model_names_no_scope() -> None:
    session = MagicMock()
    out = await entitlement_status_by_model_names(
        session,
        scope=None,
        scope_id=None,
        model_names=["a"],
    )
    assert out == {"a": "none"}


@pytest.mark.asyncio
async def test_status_for_models_with_enforceable_quota_does_not_typeerror() -> None:
    """回归：status_for_models 须与 check_and_reserve 一致调用 _quota_to_spec(q)。"""
    from dataclasses import dataclass
    from decimal import Decimal

    from domains.gateway.application.entitlement_guard import EntitlementGuard

    when = datetime(2026, 6, 18, tzinfo=UTC)
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    vkey_id = uuid.uuid4()

    @dataclass
    class _Plan:
        id: uuid.UUID
        label: str
        included_models: list[str]

    @dataclass
    class _Quota:
        id: uuid.UUID
        label: str
        window_seconds: int
        reset_strategy: str
        limit_usd: Decimal | None
        limit_tokens: int | None
        limit_requests: int | None
        limit_images: int | None
        reset_timezone: str
        reset_time_minutes: int
        reset_day_of_month: int
        enabled: bool
        valid_from: datetime | None
        valid_until: datetime | None

    plan = _Plan(id=plan_id, label="pack", included_models=["gpt-4o"])
    quota = _Quota(
        id=quota_id,
        label="daily",
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        limit_usd=None,
        limit_tokens=None,
        limit_requests=10,
        limit_images=None,
        reset_timezone="UTC",
        reset_time_minutes=0,
        reset_day_of_month=1,
        enabled=True,
        valid_from=None,
        valid_until=None,
    )

    mock_repo = MagicMock()
    mock_repo.list_for_scope = AsyncMock(return_value=[plan])
    mock_repo.list_quotas = AsyncMock(return_value=[quota])

    mock_quota = MagicMock()
    mock_quota.snapshot = AsyncMock(return_value=[])

    guard = EntitlementGuard(MagicMock(), quota_service=mock_quota)
    guard._repo = mock_repo  # type: ignore[method-assign]

    result = await guard.status_for_models(
        ENTITLEMENT_SCOPE_VKEY,
        vkey_id,
        ["gpt-4o"],
        now=when,
    )

    assert result == {"gpt-4o": "active"}
    mock_quota.snapshot.assert_awaited_once()
