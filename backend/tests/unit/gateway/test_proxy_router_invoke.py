"""``invoke_router_with_direct_fallback`` 上游错误 surfaced 单测。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import litellm
import pytest

from domains.gateway.application.proxy_router_invoke import invoke_router_with_direct_fallback


@pytest.mark.asyncio
async def test_invoke_surfaces_nested_upstream_auth_from_router_wrapper() -> None:
    auth = litellm.AuthenticationError(
        message="The API key doesn't exist",
        llm_provider="volcengine",
        model="GLM-5.1",
    )
    wrapper = litellm.BadRequestError(
        message="no healthy deployments for model=gw/t/x/m",
        model="gw/t/x/m",
        llm_provider="",
    )
    wrapper.__cause__ = auth

    guard = MagicMock()
    guard.release_budget_reservations = AsyncMock()
    guard.release_entitlement_reservations = AsyncMock()
    litellm_client = MagicMock()
    litellm_client.should_use_internal_direct_litellm = AsyncMock(return_value=False)
    ctx = MagicMock()

    with pytest.raises(litellm.AuthenticationError) as raised:
        await invoke_router_with_direct_fallback(
            guard=guard,
            litellm=litellm_client,
            ctx=ctx,
            model="m1",
            reservations=[],
            use_direct=False,
            direct_call=AsyncMock(),
            router_call=AsyncMock(side_effect=wrapper),
        )

    assert raised.value is auth
    guard.release_budget_reservations.assert_awaited_once()
    guard.release_entitlement_reservations.assert_awaited_once()


@pytest.mark.asyncio
async def test_invoke_surfaces_probed_upstream_when_router_wrapper_has_no_chain() -> None:
    wrapper = litellm.BadRequestError(
        message="no healthy deployments for model=gw/t/x/m",
        model="gw/t/x/m",
        llm_provider="",
    )
    probed = litellm.AuthenticationError(
        message="invalid api key",
        llm_provider="openai",
        model="gpt-4o",
    )

    guard = MagicMock()
    guard.release_budget_reservations = AsyncMock()
    guard.release_entitlement_reservations = AsyncMock()
    litellm_client = MagicMock()
    litellm_client.should_use_internal_direct_litellm = AsyncMock(return_value=False)
    ctx = MagicMock()
    upstream_probe = AsyncMock(return_value=probed)

    with pytest.raises(litellm.AuthenticationError) as raised:
        await invoke_router_with_direct_fallback(
            guard=guard,
            litellm=litellm_client,
            ctx=ctx,
            model="m1",
            reservations=[],
            use_direct=False,
            direct_call=AsyncMock(),
            router_call=AsyncMock(side_effect=wrapper),
            upstream_probe=upstream_probe,
        )

    assert raised.value is probed
    upstream_probe.assert_awaited_once()


@pytest.mark.asyncio
async def test_invoke_ignores_non_reportable_probe_result() -> None:
    wrapper = litellm.BadRequestError(
        message="no healthy deployments for model=gw/t/x/m",
        model="gw/t/x/m",
        llm_provider="",
    )

    guard = MagicMock()
    guard.release_budget_reservations = AsyncMock()
    guard.release_entitlement_reservations = AsyncMock()
    litellm_client = MagicMock()
    litellm_client.should_use_internal_direct_litellm = AsyncMock(return_value=False)
    ctx = MagicMock()

    with pytest.raises(litellm.BadRequestError):
        await invoke_router_with_direct_fallback(
            guard=guard,
            litellm=litellm_client,
            ctx=ctx,
            model="m1",
            reservations=[],
            use_direct=False,
            direct_call=AsyncMock(),
            router_call=AsyncMock(side_effect=wrapper),
            upstream_probe=AsyncMock(return_value=ValueError("local")),
        )
