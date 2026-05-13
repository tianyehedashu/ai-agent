"""ProxyUseCase budget reservation behavior."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application import proxy_use_case
from domains.gateway.application.budget_service import BudgetCheckResult, BudgetService
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.types import GatewayCapability


@dataclass(frozen=True)
class FakeBudget:
    limit_usd: Decimal | None = Decimal("100")
    limit_tokens: int | None = 100_000
    limit_requests: int | None = 100


class RecordingBudgetService(BudgetService):
    def __init__(self) -> None:
        super().__init__()
        self.reserved: list[tuple[str, str | None, str]] = []
        self.released: list[tuple[str, str | None, str]] = []

    async def check_rate_limit(self, **_kwargs: object) -> None:
        return None

    async def check_budget(self, **_kwargs: object) -> BudgetCheckResult:
        return BudgetCheckResult(allowed=True)

    async def reserve(
        self,
        *,
        scope: str,
        scope_id: str | None,
        period: str,
        limit_requests: int | None,
    ) -> None:
        _ = limit_requests
        self.reserved.append((scope, scope_id, period))

    async def release(
        self,
        *,
        scope: str,
        scope_id: str | None,
        period: str,
    ) -> None:
        self.released.append((scope, scope_id, period))

    async def commit(self, **_kwargs: object) -> None:
        return None


class FakeBudgetRepository:
    def __init__(self, _session: AsyncSession) -> None:
        self._session = _session

    async def get_for(
        self,
        scope: str,
        scope_id: uuid.UUID | None,
        period: str,
    ) -> FakeBudget | None:
        if scope in {"team", "user"} and scope_id is not None and period in {
            "daily",
            "monthly",
        }:
            return FakeBudget()
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_failure_releases_all_request_reservations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    budget = RecordingBudgetService()
    session = cast("AsyncSession", object())
    use_case = ProxyUseCase(session, budget_service=budget)

    async def use_direct(_ctx: ProxyContext, _model: str) -> bool:
        return True

    async def fail_direct(_kwargs: dict[str, object]) -> object:
        raise RuntimeError("upstream failed")

    async def build_metadata(
        _ctx: ProxyContext, *, user_kwargs: dict[str, object] | None = None
    ) -> dict[str, object]:
        _ = user_kwargs
        return {}

    monkeypatch.setattr(proxy_use_case, "BudgetRepository", FakeBudgetRepository)
    monkeypatch.setattr(use_case, "_should_use_internal_direct_litellm", use_direct)
    monkeypatch.setattr(use_case, "_direct_chat_completion", fail_direct)
    monkeypatch.setattr(use_case, "_build_metadata", build_metadata)

    ctx = ProxyContext(
        team_id=team_id,
        user_id=user_id,
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id=str(uuid.uuid4()),
        store_full_messages=False,
        guardrail_enabled=True,
    )

    with pytest.raises(RuntimeError, match="upstream failed"):
        await use_case.chat_completion(
            ctx,
            {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )

    expected = [
        ("team", str(team_id), "daily"),
        ("team", str(team_id), "monthly"),
        ("user", str(user_id), "daily"),
        ("user", str(user_id), "monthly"),
    ]
    assert budget.reserved == expected
    assert budget.released == expected
