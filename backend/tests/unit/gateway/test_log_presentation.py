"""log_presentation 角色遮罩。"""

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from domains.gateway.application.management.log_presentation import request_log_to_dict
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.tenancy.domain.management_context import ManagementTeamContext


def _fake_log() -> GatewayRequestLog:
    return GatewayRequestLog(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        team_id=uuid.uuid4(),
        capability="chat",
        status="success",
        input_tokens=1,
        output_tokens=2,
        cost_usd=Decimal("0.01"),
        revenue_usd=Decimal("0.02"),
        latency_ms=10,
        pricing_snapshot={"upstream_cost_usd": 0.01, "downstream_revenue_usd": 0.02},
    )


def test_member_masks_upstream_cost() -> None:
    record = _fake_log()
    team = ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="shared",
        team_role="member",
        user_id=uuid.uuid4(),
        is_platform_admin=False,
    )
    data = request_log_to_dict(record, team)
    assert data["cost_usd"] == Decimal("0")
    snap = data.get("pricing_snapshot")
    assert isinstance(snap, dict)
    assert "upstream_cost_usd" not in snap


def test_admin_keeps_cost() -> None:
    record = _fake_log()
    team = ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="shared",
        team_role="admin",
        user_id=uuid.uuid4(),
        is_platform_admin=False,
    )
    data = request_log_to_dict(record, team)
    assert data["cost_usd"] == Decimal("0.01")


def test_orm_row_to_dict_skips_unloaded_columns() -> None:
    """列表 defer 的大字段未加载时不应出现在 dict 中（且不得触发 lazy load）。"""
    record = _fake_log()
    data = request_log_to_dict(
        record,
        ManagementTeamContext(
            team_id=uuid.uuid4(),
            team_kind="shared",
            team_role="admin",
            user_id=uuid.uuid4(),
            is_platform_admin=True,
        ),
    )
    assert "id" in data
    assert "prompt_redacted" not in data
