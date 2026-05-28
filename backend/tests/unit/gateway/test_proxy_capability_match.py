"""ProxyUseCase：模型主调用面与 HTTP 入口 capability 对齐校验。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.errors import CapabilityNotAllowedError
from domains.gateway.domain.types import GatewayCapability


def _resolved(capability: str, *, route_name: str | None = None) -> ResolvedModelName:
    record = MagicMock()
    record.capability = capability
    record.id = uuid.uuid4()
    record.provider = "openai"
    record.real_model = "gpt-4o-mini"
    route = None
    if route_name is not None:
        route = MagicMock()
        route.virtual_model = route_name
    return ResolvedModelName(record=record, route=route, via_route=route_name)


@pytest.mark.asyncio
async def test_chat_rejects_video_generation_model(db_session: Any) -> None:
    tid = uuid.uuid4()
    ctx = ProxyContext(
        team_id=tid,
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    uc = ProxyUseCase(db_session)
    with (
        patch(
            "domains.gateway.application.proxy_guard.resolve_model_or_route",
            AsyncMock(return_value=_resolved("video_generation")),
        ),
        pytest.raises(CapabilityNotAllowedError) as exc_info,
    ):
        await uc.guard.assert_request_capability_matches_model(ctx, "my-video-model")
    assert "video_generation" in str(exc_info.value)
    assert "chat" in str(exc_info.value)


@pytest.mark.asyncio
async def test_chat_allows_matching_capability(db_session: Any) -> None:
    tid = uuid.uuid4()
    ctx = ProxyContext(
        team_id=tid,
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    uc = ProxyUseCase(db_session)
    with patch(
        "domains.gateway.application.proxy_guard.resolve_model_or_route",
        AsyncMock(return_value=_resolved("chat")),
    ):
        await uc.guard.assert_request_capability_matches_model(ctx, "my-chat-model")


@pytest.mark.asyncio
async def test_skips_when_model_not_registered(db_session: Any) -> None:
    tid = uuid.uuid4()
    ctx = ProxyContext(
        team_id=tid,
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    uc = ProxyUseCase(db_session)
    with patch(
        "domains.gateway.application.proxy_guard.resolve_model_or_route",
        AsyncMock(return_value=None),
    ):
        await uc.guard.assert_request_capability_matches_model(ctx, "unknown-alias")


@pytest.mark.asyncio
async def test_virtual_route_capability_mismatch_message_uses_route_label(db_session: Any) -> None:
    tid = uuid.uuid4()
    ctx = ProxyContext(
        team_id=tid,
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    uc = ProxyUseCase(db_session)
    with (
        patch(
            "domains.gateway.application.proxy_guard.resolve_model_or_route",
            AsyncMock(return_value=_resolved("image", route_name="my-route")),
        ),
        pytest.raises(CapabilityNotAllowedError) as exc_info,
    ):
        await uc.guard.assert_request_capability_matches_model(ctx, "my-route")
    assert "虚拟路由" in str(exc_info.value)
