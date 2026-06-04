"""代理端 /v1/models 列表组装单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest

from domains.gateway.application.proxy_model_list_reads import (
    _aggregate_connectivity,
    _aggregate_entitlement,
    _build_route_model_list_item,
    build_openai_model_list_item,
)
from domains.gateway.domain.types import EntitlementListStatus
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute


def _row(
    *,
    name: str = "dashscope/qwen-max",
    last_test_status: str | None = None,
    last_test_reason: str | None = None,
) -> GatewayModel:
    tested_at = datetime(2026, 5, 18, 10, 0, 0, tzinfo=UTC) if last_test_status else None
    return GatewayModel(
        name=name,
        capability="chat",
        real_model="dashscope/qwen-max",
        credential_id=uuid.uuid4(),
        provider="dashscope",
        tags={"display_name": "Qwen Max"},
        last_test_status=last_test_status,
        last_tested_at=tested_at,
        last_test_reason=last_test_reason,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_build_openai_model_list_item_includes_gateway_metadata() -> None:
    item = build_openai_model_list_item(_row(), entitlement_status="none")
    assert item["id"] == "dashscope/qwen-max"
    assert item["object"] == "model"
    assert item["capability"] == "chat"
    assert item["model_types"] == ["text"]
    gateway = item["gateway"]
    assert isinstance(gateway, dict)
    assert gateway["display_name"] == "Qwen Max"
    assert gateway["real_model"] == "dashscope/qwen-max"
    assert gateway["connectivity_status"] is None
    assert gateway["connectivity_tested_at"] is None
    assert gateway["entitlement_status"] == "none"
    assert gateway["callable"] is True


def test_build_openai_model_list_item_failed_connectivity_not_callable() -> None:
    item = build_openai_model_list_item(
        _row(last_test_status="failed", last_test_reason="upstream error"),
        entitlement_status="active",
    )
    gateway = item["gateway"]
    assert gateway["connectivity_status"] == "failed"
    assert gateway["connectivity_reason"] == "upstream error"
    assert gateway["connectivity_tested_at"] is not None
    assert gateway["callable"] is False


@pytest.mark.parametrize(
    ("entitlement_status", "expected_callable"),
    [
        ("exhausted", False),
        ("expired", False),
        ("resetting", True),
        ("active", True),
        ("none", True),
    ],
)
def test_build_openai_model_list_item_entitlement_blocks_callable(
    entitlement_status: EntitlementListStatus,
    expected_callable: bool,
) -> None:
    item = build_openai_model_list_item(_row(), entitlement_status=entitlement_status)
    assert item["gateway"]["callable"] is expected_callable


# ---------------------------------------------------------------------------
# Route aggregation helpers
# ---------------------------------------------------------------------------


def test_aggregate_connectivity_any_success_is_success() -> None:
    models = [
        _row(last_test_status="success"),
        _row(last_test_status="failed"),
    ]
    assert _aggregate_connectivity(models) == "success"


def test_aggregate_connectivity_all_failed_is_failed() -> None:
    models = [
        _row(last_test_status="failed"),
        _row(last_test_status="failed"),
    ]
    assert _aggregate_connectivity(models) == "failed"


def test_aggregate_connectivity_all_none_is_none() -> None:
    models = [_row(), _row()]
    assert _aggregate_connectivity(models) is None


def test_aggregate_entitlement_any_active_is_active() -> None:
    models = [_row(name="m1"), _row(name="m2")]
    entitlement = {"m1": "exhausted", "m2": "active"}
    assert _aggregate_entitlement(models, entitlement) == "active"


def test_aggregate_entitlement_priority_resetting_exhausted_expired() -> None:
    models = [_row(name="m1"), _row(name="m2")]
    assert _aggregate_entitlement(models, {"m1": "resetting", "m2": "exhausted"}) == "resetting"
    assert _aggregate_entitlement(models, {"m1": "exhausted", "m2": "expired"}) == "exhausted"
    assert _aggregate_entitlement(models, {"m1": "expired", "m2": "none"}) == "expired"
    assert _aggregate_entitlement(models, {"m1": "none", "m2": "none"}) == "none"


# ---------------------------------------------------------------------------
# Route model list item
# ---------------------------------------------------------------------------


def test_build_route_model_list_item_basic() -> None:
    m1 = _row(name="deepseek-chat--a1b2c3d4", last_test_status="success")
    route = GatewayRoute(
        tenant_id=uuid.uuid4(),
        virtual_model="deepseek-chat",
        primary_models=["deepseek-chat--a1b2c3d4"],
        strategy="simple-shuffle",
    )
    item = _build_route_model_list_item(
        route,
        {"deepseek-chat--a1b2c3d4": m1},
        {"deepseek-chat--a1b2c3d4": "active"},
    )
    assert item is not None
    assert item["id"] == "deepseek-chat"
    assert item["object"] == "model"
    assert item["gateway"]["display_name"] == "deepseek-chat"
    assert item["gateway"]["connectivity_status"] == "success"
    assert item["gateway"]["entitlement_status"] == "active"
    assert item["gateway"]["callable"] is True


def test_build_route_model_list_item_missing_models_returns_none() -> None:
    route = GatewayRoute(
        tenant_id=uuid.uuid4(),
        virtual_model="x",
        primary_models=["missing-model"],
        strategy="simple-shuffle",
    )
    item = _build_route_model_list_item(route, {}, {})
    assert item is None


def test_build_route_model_list_item_empty_primary_returns_none() -> None:
    route = GatewayRoute(
        tenant_id=uuid.uuid4(),
        virtual_model="x",
        primary_models=[],
        strategy="simple-shuffle",
    )
    item = _build_route_model_list_item(route, {}, {})
    assert item is None
