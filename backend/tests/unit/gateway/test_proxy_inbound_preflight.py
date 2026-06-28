"""run_proxy_inbound_preflight 统一入站护栏。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.catalog.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.proxy.proxy_inbound_preflight import run_proxy_inbound_preflight
from domains.gateway.application.proxy.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.errors import (
    BudgetExceededError,
    CapabilityNotAllowedError,
    GatewayModelNotFoundError,
)
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
            "domains.gateway.application.proxy.proxy_guard.resolve_model_or_route",
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
    from domains.gateway.application.proxy import proxy_guard as proxy_guard_module

    class _NoBudgetRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_for(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def get_many_by_plan(self, _plan: object) -> dict[object, object]:
            return {}

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


def _mock_guard(resolved: ResolvedModelName | None, *, exempt: bool) -> MagicMock:
    guard = MagicMock()
    guard.check_model = MagicMock()
    guard.resolve_and_validate_request_model = AsyncMock(return_value=resolved)
    guard.check_capability = MagicMock()
    guard.check_limits = AsyncMock()
    guard.is_platform_budget_exempt = AsyncMock(return_value=exempt)
    guard.check_budget = AsyncMock(return_value=["phase1"])
    guard.check_entitlement = AsyncMock()
    guard.release_budget_reservations = AsyncMock()
    return guard


def _chat_ctx() -> ProxyContext:
    return ProxyContext(
        team_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=False,
    )


@pytest.mark.asyncio
async def test_personal_team_model_skips_all_platform_budget() -> None:
    resolved = _resolved("chat")
    guard = _mock_guard(resolved, exempt=True)
    result = await run_proxy_inbound_preflight(
        guard, _chat_ctx(), capability=GatewayCapability.CHAT, model="my-byok-model"
    )
    assert result.reservations == []
    guard.check_budget.assert_not_awaited()


@pytest.mark.asyncio
async def test_shared_team_model_still_runs_phase1_budget() -> None:
    resolved = _resolved("chat")
    guard = _mock_guard(resolved, exempt=False)
    result = await run_proxy_inbound_preflight(
        guard, _chat_ctx(), capability=GatewayCapability.CHAT, model="team-model"
    )
    assert result.reservations == ["phase1"]
    guard.check_budget.assert_awaited_once()


@pytest.mark.asyncio
async def test_preflight_failure_schedules_request_log() -> None:
    guard = _mock_guard(_resolved("chat"), exempt=False)
    guard.check_budget = AsyncMock(
        side_effect=BudgetExceededError(scope="team", period="daily", limit=1.0, used=1.0)
    )
    ctx = _chat_ctx()
    with (
        patch(
            "domains.gateway.application.proxy.proxy_inbound_preflight.schedule_preflight_failure_log",
        ) as schedule_log,
        pytest.raises(BudgetExceededError),
    ):
        await run_proxy_inbound_preflight(
            guard, ctx, capability=GatewayCapability.CHAT, model="team-model"
        )
    schedule_log.assert_called_once()
    assert schedule_log.call_args.args[0] is ctx
    assert isinstance(schedule_log.call_args.args[1], BudgetExceededError)


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
            "domains.gateway.application.proxy.proxy_guard.resolve_model_or_route",
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
