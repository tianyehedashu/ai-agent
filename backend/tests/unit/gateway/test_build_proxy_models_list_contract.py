"""build_proxy_models_list 契约校验单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest

from domains.gateway.application.proxy.proxy_model_list_reads import build_proxy_models_list
from domains.gateway.infrastructure.models.gateway_model import GatewayModel


def _row(name: str = "m1") -> GatewayModel:
    return GatewayModel(
        name=name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=uuid.uuid4(),
        provider="openai",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_build_proxy_models_list_rejects_mismatched_model_list_ids(
    db_session,
) -> None:
    with pytest.raises(ValueError, match="model_list_ids length"):
        await build_proxy_models_list(
            db_session,
            [_row()],
            entitlement_scope=None,
            entitlement_scope_id=None,
            model_list_ids=["a", "b"],
        )
