"""ProxyUseCase：模型主调用面与 HTTP 入口 capability 对齐校验。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.errors import CapabilityNotAllowedError
from domains.gateway.domain.types import GatewayCapability


@pytest.mark.asyncio
async def test_chat_rejects_video_generation_model(db_session: Any) -> None:
    tid = uuid.uuid4()
    model_row = MagicMock()
    model_row.capability = "video_generation"
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
    with patch.object(
        ProxyUseCase,
        "_assert_request_capability_matches_model",
        wraps=uc._assert_request_capability_matches_model,
    ), patch(
        "domains.gateway.application.proxy_use_case.GatewayModelRepository"
    ) as repo_cls:
        repo_cls.return_value.get_by_name = AsyncMock(return_value=model_row)
        with pytest.raises(CapabilityNotAllowedError) as exc_info:
            await uc._assert_request_capability_matches_model(ctx, "my-video-model")
    assert "video_generation" in str(exc_info.value)
    assert "chat" in str(exc_info.value)


@pytest.mark.asyncio
async def test_chat_allows_matching_capability(db_session: Any) -> None:
    tid = uuid.uuid4()
    model_row = MagicMock()
    model_row.capability = "chat"
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
        "domains.gateway.application.proxy_use_case.GatewayModelRepository"
    ) as repo_cls:
        repo_cls.return_value.get_by_name = AsyncMock(return_value=model_row)
        await uc._assert_request_capability_matches_model(ctx, "my-chat-model")


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
        "domains.gateway.application.proxy_use_case.GatewayModelRepository"
    ) as repo_cls:
        repo_cls.return_value.get_by_name = AsyncMock(return_value=None)
        await uc._assert_request_capability_matches_model(ctx, "unknown-alias")
