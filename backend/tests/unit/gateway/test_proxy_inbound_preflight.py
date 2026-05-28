"""run_proxy_inbound_preflight 统一入站护栏。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.proxy_inbound_preflight import run_proxy_inbound_preflight
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.errors import CapabilityNotAllowedError, GatewayModelNotFoundError
from domains.gateway.domain.types import GatewayCapability


def _resolved(capability: str) -> ResolvedModelName:
    record = MagicMock()
    record.capability = capability
    return ResolvedModelName(record=record, route=None, via_route=None)


@pytest.mark.asyncio
async def test_embedding_preflight_rejects_chat_registered_model(db_session: Any) -> None:
    ctx = ProxyContext(
        team_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.EMBEDDING,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    uc = ProxyUseCase(db_session)
    with (
        patch(
            "domains.gateway.application.proxy_guard.resolve_model_or_route",
            AsyncMock(return_value=_resolved("chat")),
        ),
        pytest.raises(CapabilityNotAllowedError),
    ):
        await run_proxy_inbound_preflight(
            uc.guard,
            ctx,
            capability=GatewayCapability.EMBEDDING,
            model="text-embedding-model",
            require_model=True,
        )


@pytest.mark.asyncio
async def test_optional_model_skips_model_whitelist(
    db_session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from domains.gateway.application import proxy_guard as proxy_guard_module

    class _NoBudgetRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_for(self, *_args: object, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(
        proxy_guard_module,
        "_default_budget_repository_factory",
        lambda session: _NoBudgetRepo(session),
    )

    ctx = ProxyContext(
        team_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.RERANK,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
        allowed_models=("only-this",),
    )
    uc = ProxyUseCase(db_session)
    result = await run_proxy_inbound_preflight(
        uc.guard,
        ctx,
        capability=GatewayCapability.RERANK,
        model=None,
    )
    assert result.model is None
    assert result.reservations == []


@pytest.mark.asyncio
async def test_preflight_rejects_unregistered_model(db_session: Any) -> None:
    ctx = ProxyContext(
        team_id=uuid.uuid4(),
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
            AsyncMock(return_value=None),
        ),
        pytest.raises(GatewayModelNotFoundError, match="deepseek-v4-flash"),
    ):
        await run_proxy_inbound_preflight(
            uc.guard,
            ctx,
            capability=GatewayCapability.CHAT,
            model="deepseek-v4-flash-260425",
            require_model=True,
        )
