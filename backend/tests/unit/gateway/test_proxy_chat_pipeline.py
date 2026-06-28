"""prepare_chat_proxy_request 公共流水线单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.catalog.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.proxy.proxy_chat_pipeline import prepare_chat_proxy_request
from domains.gateway.application.proxy.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.types import GatewayCapability


def _preflight_result(*, model: str = "gpt-4o") -> MagicMock:
    resolved = ResolvedModelName(
        record=MagicMock(tags={}, upstream_call_shape=None),
        route=None,
        via_route=None,
    )
    result = MagicMock()
    result.model = model
    result.reservations = []
    result.resolved = resolved
    return result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_prepare_chat_passes_kwargs_only_to_vision_inline(db_session: object) -> None:
    """调用指南 / Playground Chat 路径：vision 内联只收 kwargs，不传 session。"""
    ctx = ProxyContext(
        team_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    use_case = ProxyUseCase(db_session)  # type: ignore[arg-type]
    litellm_kwargs = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "hello"}],
        "metadata": {"gateway_request_id": "rid"},
    }
    prepared_litellm = MagicMock(resolved=_preflight_result().resolved)

    with (
        patch(
            "domains.gateway.application.proxy.proxy_chat_pipeline.run_proxy_inbound_preflight",
            AsyncMock(return_value=_preflight_result()),
        ),
        patch.object(
            use_case,
            "prepare_litellm_invoke",
            AsyncMock(return_value=(prepared_litellm, dict(litellm_kwargs))),
        ),
        patch(
            "domains.gateway.application.proxy.proxy_chat_pipeline.inline_vision_image_urls_in_kwargs",
            AsyncMock(side_effect=lambda kw: kw),
        ) as inline_mock,
    ):
        prepared = await prepare_chat_proxy_request(
            use_case,
            ctx,
            {"model": "gpt-4o", "messages": litellm_kwargs["messages"]},
            estimate_tokens=32,
        )

    inline_mock.assert_awaited_once()
    call_args, call_kwargs = inline_mock.await_args_list[0]
    assert len(call_args) == 1
    assert call_args[0]["messages"] == litellm_kwargs["messages"]
    assert call_kwargs == {}
    assert prepared.kwargs["messages"] == litellm_kwargs["messages"]
