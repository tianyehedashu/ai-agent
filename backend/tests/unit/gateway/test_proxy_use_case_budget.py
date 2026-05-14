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
    model_name: str | None = None


class RecordingBudgetService(BudgetService):
    def __init__(self) -> None:
        super().__init__()
        self.reserved: list[tuple[str, str | None, str, str | None]] = []
        self.released: list[tuple[str, str | None, str, str | None]] = []

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
        budget_model_name: str | None = None,
    ) -> None:
        _ = limit_requests
        self.reserved.append((scope, scope_id, period, budget_model_name))

    async def release(
        self,
        *,
        scope: str,
        scope_id: str | None,
        period: str,
        budget_model_name: str | None = None,
    ) -> None:
        self.released.append((scope, scope_id, period, budget_model_name))

    async def commit(self, **_kwargs: object) -> None:
        return None


class CommitRecordingBudgetService(BudgetService):
    """记录 commit 调用（不连 Redis）。"""

    def __init__(self) -> None:
        super().__init__()
        self.commits: list[tuple[str, str | None, str, str | None, int, Decimal]] = []

    async def check_rate_limit(self, **_kwargs: object) -> None:
        return None

    async def check_budget(self, **_kwargs: object) -> BudgetCheckResult:
        return BudgetCheckResult(allowed=True)

    async def reserve(self, **_kwargs: object) -> None:
        return None

    async def release(self, **_kwargs: object) -> None:
        return None

    async def commit(
        self,
        *,
        scope: str,
        scope_id: str | None,
        period: str,
        delta_cost: Decimal,
        delta_tokens: int,
        budget_model_name: str | None = None,
    ) -> None:
        self.commits.append(
            (scope, scope_id, period, budget_model_name, delta_tokens, delta_cost)
        )


class FakeBudgetRepository:
    def __init__(self, _session: AsyncSession) -> None:
        self._session = _session

    async def get_for(
        self,
        scope: str,
        scope_id: uuid.UUID | None,
        period: str,
        *,
        model_name: str | None = None,
    ) -> FakeBudget | None:
        if scope in {"team", "user"} and scope_id is not None and period in {
            "daily",
            "monthly",
            "total",
        }:
            if model_name is None:
                return FakeBudget(model_name=None)
            if model_name == "gpt-4o-mini":
                return FakeBudget(model_name="gpt-4o-mini")
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

    periods = ("daily", "monthly", "total")
    expected: list[tuple[str, str | None, str, str | None]] = []
    for scope, sid in (("team", str(team_id)), ("user", str(user_id))):
        for period in periods:
            expected.append((scope, sid, period, None))
            expected.append((scope, sid, period, "gpt-4o-mini"))
    assert budget.reserved == expected
    assert budget.released == expected


class _DummySessionCM:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_settle_usage_commits_aggregate_and_model_redis_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """结算对 team 维度同时写入汇总桶 (None) 与模型桶 (budget_model 字符串)。"""
    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=None,
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id=str(uuid.uuid4()),
        store_full_messages=False,
        guardrail_enabled=True,
        budget_model="gpt-4o-mini",
    )
    budget = CommitRecordingBudgetService()
    fixed_id = uuid.uuid4()

    class _Row:
        id = fixed_id

    class _FakeSettleRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_for(
            self,
            scope: str,
            scope_uuid: uuid.UUID,
            period: str,
            *,
            model_name: str | None = None,
        ) -> _Row | None:
            if scope != "team" or scope_uuid != team_id:
                return None
            if period not in {"daily", "monthly", "total"}:
                return None
            if model_name is None or model_name == "gpt-4o-mini":
                return _Row()
            return None

        async def settle_usage(
            self,
            _budget_id: uuid.UUID,
            *,
            delta_usd: Decimal,
            delta_tokens: int,
            delta_requests: int,
        ) -> None:
            _ = delta_usd
            _ = delta_tokens
            _ = delta_requests

    monkeypatch.setattr(proxy_use_case, "get_session_context", lambda: _DummySessionCM())
    monkeypatch.setattr(proxy_use_case, "BudgetRepository", _FakeSettleRepo)

    await proxy_use_case._settle_usage(
        ctx,
        budget,
        tokens=7,
        cost=Decimal("0.02"),
        requests=1,
    )

    periods = ("daily", "monthly", "total")
    want: list[tuple[str, str | None, str, str | None, int, Decimal]] = []
    sid = str(team_id)
    for period in periods:
        want.append(("team", sid, period, None, 7, Decimal("0.02")))
        want.append(("team", sid, period, "gpt-4o-mini", 7, Decimal("0.02")))
    for row in want:
        assert row in budget.commits
    assert len(budget.commits) == len(want)
