"""proxy_metadata_builder 跨团队派发 metadata 单测。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.proxy.proxy_context import ProxyContext
from domains.gateway.application.proxy.proxy_metadata_builder import ProxyMetadataBuilder
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal


@pytest.mark.asyncio
async def test_build_metadata_client_raw_model_in_route_name(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Any,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.proxy.proxy_metadata_builder.TeamService.get_team",
        AsyncMock(return_value=MagicMock(name="t", kind="personal")),
    )
    monkeypatch.setattr(
        ProxyMetadataBuilder,
        "credential_metadata_for_virtual_model",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        "domains.gateway.application.proxy.proxy_metadata_builder.get_route_snapshot_metadata",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "domains.gateway.application.proxy.proxy_metadata_builder.attach_downstream_pricing_metadata",
        AsyncMock(),
    )

    owner_team = uuid.uuid4()
    effective_team = uuid.uuid4()
    vkey = VirtualKeyPrincipal(
        vkey_id=uuid.uuid4(),
        vkey_name="k",
        team_id=owner_team,
        user_id=uuid.uuid4(),
        allowed_models=(),
        allowed_capabilities=(GatewayCapability.CHAT,),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
        is_system=False,
        granted_team_ids=(owner_team, effective_team),
    )
    ctx = ProxyContext(
        team_id=effective_team,
        user_id=vkey.user_id,
        vkey=vkey,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
        client_raw_model="team-y/gpt-4o",
        dispatched_via_prefix=True,
    )
    meta = await ProxyMetadataBuilder(db_session).build(
        ctx,
        user_kwargs={"model": "gpt-4o"},
    )
    assert meta["gateway_route_name"] == "team-y/gpt-4o"
    assert meta["gateway_route_name_normalized"] == "gpt-4o"
    assert meta["gateway_dispatched_via_prefix"] is True
    assert meta["gateway_vkey_owner_team_id"] == str(owner_team)
