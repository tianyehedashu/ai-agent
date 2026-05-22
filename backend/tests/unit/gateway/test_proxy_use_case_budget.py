"""ProxyUseCase budget reservation behavior."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application import proxy_guard, proxy_response_adapter
from domains.gateway.application.budget_service import BudgetCheckResult, BudgetService
from domains.gateway.application.proxy_response_adapter import settle_usage
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
        target_kind: str,
        target_id: str | None,
        period: str,
        limit_requests: int | None,
        budget_model_name: str | None = None,
    ) -> None:
        _ = limit_requests
        self.reserved.append((target_kind, target_id, period, budget_model_name))

    async def release(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        budget_model_name: str | None = None,
    ) -> None:
        self.released.append((target_kind, target_id, period, budget_model_name))

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
        target_kind: str,
        target_id: str | None,
        period: str,
        delta_cost: Decimal,
        delta_tokens: int,
        budget_model_name: str | None = None,
    ) -> None:
        self.commits.append(
            (target_kind, target_id, period, budget_model_name, delta_tokens, delta_cost)
        )


class FakeBudgetRepository:
    def __init__(self, _session: AsyncSession) -> None:
        self._session = _session

    async def get_for(
        self,
        target_kind: str,
        target_id: uuid.UUID | None,
        period: str,
        *,
        model_name: str | None = None,
    ) -> FakeBudget | None:
        if (
            target_kind in {"tenant", "user"}
            and target_id is not None
            and period
            in {
                "daily",
                "monthly",
                "total",
            }
        ):
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

    async def prepare_litellm_kwargs(
        _ctx: ProxyContext, body: dict[str, object]
    ) -> dict[str, object]:
        return {**body, "metadata": {}}

    async def _none_resolve(
        _session: object, _team_id: object, _name: str, *, user_id: object | None = None
    ) -> None:
        _ = user_id
        return None

    monkeypatch.setattr(proxy_guard, "BudgetRepository", FakeBudgetRepository)
    monkeypatch.setattr(proxy_guard, "resolve_model_or_route", _none_resolve)
    monkeypatch.setattr(
        use_case.litellm, "should_use_internal_direct_litellm", use_direct
    )
    monkeypatch.setattr(use_case.litellm, "direct_chat_completion", fail_direct)
    monkeypatch.setattr(use_case, "prepare_litellm_kwargs", prepare_litellm_kwargs)

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
    for kind, sid in (("tenant", str(team_id)), ("user", str(user_id))):
        for period in periods:
            expected.append((kind, sid, period, None))
            expected.append((kind, sid, period, "gpt-4o-mini"))
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
            target_kind: str,
            target_uuid: uuid.UUID,
            period: str,
            *,
            model_name: str | None = None,
        ) -> _Row | None:
            if target_kind != "tenant" or target_uuid != team_id:
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

    monkeypatch.setattr(proxy_response_adapter, "get_session_context", lambda: _DummySessionCM())
    monkeypatch.setattr(proxy_response_adapter, "BudgetRepository", _FakeSettleRepo)

    await settle_usage(
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
        want.append(("tenant", sid, period, None, 7, Decimal("0.02")))
        want.append(("tenant", sid, period, "gpt-4o-mini", 7, Decimal("0.02")))
    for row in want:
        assert row in budget.commits
    assert len(budget.commits) == len(want)
