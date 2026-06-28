"""个人模型列表 selector_capabilities 暴露。"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from domains.gateway.application.catalog.personal_models import gateway_model_to_personal_list_item
from domains.gateway.infrastructure.models.gateway_model import GatewayModel


def test_personal_list_item_includes_selector_capabilities() -> None:
    row = GatewayModel(
        id=uuid.uuid4(),
        name="my-claude-opus",
        capability="chat",
        real_model="claude-opus-4-7",
        provider="anthropic",
        credential_id=uuid.uuid4(),
        weight=1,
        enabled=True,
        tags={
            "display_name": "My Claude",
            "supports_reasoning": True,
            "thinking_param": "anthropic_extended",
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    item = gateway_model_to_personal_list_item(row)
    sc = item["selector_capabilities"]
    assert sc["thinking_param"] == "anthropic_extended"
    assert sc["supports_reasoning"] is True
