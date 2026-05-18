"""代理端 /v1/models 列表组装单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest

from domains.gateway.application.proxy_model_list_reads import (
    build_openai_model_list_item,
)
from domains.gateway.domain.types import EntitlementListStatus
from domains.gateway.infrastructure.models.gateway_model import GatewayModel


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
