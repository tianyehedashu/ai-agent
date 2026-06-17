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
from domains.gateway.application.proxy_context import PlatformBudgetPreflightState
from domains.gateway.application.proxy_metadata_builder import PreparedLitellmKwargs
from domains.gateway.application.proxy_response_adapter import settle_usage
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.proxy_policy import BudgetReservation
from domains.gateway.domain.types import GatewayCapability


@dataclass(frozen=True)
class FakeBudget:
    target_kind: str = "tenant"
    target_id: uuid.UUID | None = None
    period: str = "monthly"
    limit_usd: Decimal | None = Decimal("100")
    limit_tokens: int | None = 100_000
    limit_requests: int | None = 100
    model_name: str | None = None
    credential_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    period_timezone: str = "UTC"
    period_reset_minutes: int = 0
    period_reset_day: int = 1


class RecordingBudgetService(BudgetService):
    def __init__(self) -> None:
        super().__init__()
        self.reserved: list[tuple[str, str | None, str, str | None]] = []
        self.released: list[tuple[str, str | None, str, str | None]] = []

    async def check_rate_limit(self, **_kwargs: object) -> None:
        return None

    async def check_budget(self, **_kwargs: object) -> BudgetCheckResult:
        return BudgetCheckResult(allowed=True)

    async def read_budget_usage_batch(self, _coords: object) -> dict[object, object]:
        return {}

    async def reserve(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        limit_requests: int | None,
        limit_tokens: int | None = None,
        estimate_tokens: int = 0,
        budget_model_name: str | None = None,
        credential_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        **_kwargs: object,
    ) -> tuple[int, int]:
        _ = _kwargs
        _ = limit_tokens, estimate_tokens, credential_id, tenant_id
        self.reserved.append((target_kind, target_id, period, budget_model_name))
        return (1 if limit_requests else 0, 0)

    async def release(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        budget_model_name: str | None = None,
        credential_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        reserved_requests: int = 1,
        reserved_tokens: int = 0,
        **_kwargs: object,
    ) -> None:
        _ = _kwargs
        _ = reserved_requests, reserved_tokens, credential_id, tenant_id
        self.released.append((target_kind, target_id, period, budget_model_name))

    async def commit(self, **_kwargs: object) -> None:
        return None


class CommitRecordingBudgetService(BudgetService):
    """记录 commit 调用（不连 Redis）。"""

    def __init__(self) -> None:
        super().__init__()
        self.commits: list[tuple[str, str | None, str, str | None, int, Decimal]] = []
        self.releases: list[tuple[str, str | None, str, str | None, int, int]] = []

    async def check_rate_limit(self, **_kwargs: object) -> None:
        return None

    async def check_budget(self, **_kwargs: object) -> BudgetCheckResult:
        return BudgetCheckResult(allowed=True)

    async def reserve(self, **_kwargs: object) -> None:
        return None

    async def release(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        budget_model_name: str | None = None,
        reserved_requests: int = 1,
        reserved_tokens: int = 0,
        **_kwargs: object,
    ) -> None:
        self.releases.append(
            (
                target_kind,
                target_id,
                period,
                budget_model_name,
                reserved_requests,
                reserved_tokens,
            )
        )

    async def commit(
        self,
        *,
        target_kind: str,
        target_id: str | None,
        period: str,
        delta_cost: Decimal,
        delta_tokens: int,
        budget_model_name: str | None = None,
        credential_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        **_kwargs: object,
    ) -> None:
        _ = _kwargs
        self.commits.append(
            (target_kind, target_id, period, budget_model_name, delta_tokens, delta_cost)
        )


class FailingCommitBudgetService(CommitRecordingBudgetService):
    async def commit(self, **_kwargs: object) -> None:
        raise RuntimeError("redis commit failed")


class FakeBudgetRepository:
    def __init__(self, _session: AsyncSession) -> None:
        self._session = _session

    async def get_many_by_plan(
        self, plan: object
    ) -> dict[tuple[str, uuid.UUID, str, str | None], FakeBudget]:
        out: dict[tuple[str, uuid.UUID, str, str | None], FakeBudget] = {}
        for query in plan:  # type: ignore[union-attr]
            row = await self.get_for(
                query.target_kind,
                query.target_id,
                query.period,
                model_name=query.model_name,
                tenant_id=query.tenant_id,
            )
            if row is not None:
                out[
                    (
                        query.target_kind,
                        query.target_id,
                        query.period,
                        query.model_name,
                        query.credential_id,
                        query.tenant_id,
                    )
                ] = row
        return out

    async def get_for(
        self,
        target_kind: str,
        target_id: uuid.UUID | None,
        period: str,
        *,
        model_name: str | None = None,
        credential_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> FakeBudget | None:
        _ = credential_id
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
                return FakeBudget(
                    target_kind=target_kind,
                    target_id=target_id,
                    period=period,
                    model_name=None,
                    tenant_id=tenant_id,
                )
            if model_name == "gpt-4o-mini":
                return FakeBudget(
                    target_kind=target_kind,
                    target_id=target_id,
                    period=period,
                    model_name="gpt-4o-mini",
                    tenant_id=tenant_id,
                )
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

    async def use_direct(
        _ctx: ProxyContext, _model: str, *, resolved: object | None = None
    ) -> bool:
        _ = resolved
        return True

    async def fail_direct(_kwargs: dict[str, object]) -> object:
        raise RuntimeError("upstream failed")

    async def prepare_litellm_invoke(
        _ctx: ProxyContext,
        body: dict[str, object],
        *,
        resolved: object | None = None,
        timings: object | None = None,
    ) -> tuple[PreparedLitellmKwargs, dict[str, object]]:
        _ = resolved, timings
        kwargs = {**body, "metadata": {}}
        prepared = PreparedLitellmKwargs(
            kwargs=kwargs,
            client_model=str(body.get("model", "")),
            resolved=None,
        )
        return prepared, kwargs

    async def _fake_resolve(
        _session: object, _team_id: object, _name: str, *, user_id: object | None = None
    ) -> object:
        _ = user_id

        @dataclass(frozen=True)
        class _Record:
            capability: str = "chat"
            enabled: bool = True

        @dataclass(frozen=True)
        class _Resolved:
            record: _Record = _Record()
            route: None = None
            via_route: None = None

        return _Resolved()

    monkeypatch.setattr(proxy_guard, "BudgetRepository", FakeBudgetRepository)
    monkeypatch.setattr(
        proxy_guard,
        "_default_budget_repository_factory",
        lambda session: FakeBudgetRepository(session),
    )
    monkeypatch.setattr(proxy_guard, "resolve_model_or_route", _fake_resolve)

    use_case = ProxyUseCase(session, budget_service=budget)
    monkeypatch.setattr(use_case.litellm, "should_use_internal_direct_litellm", use_direct)
    monkeypatch.setattr(use_case.litellm, "direct_chat_completion", fail_direct)
    monkeypatch.setattr(use_case, "prepare_litellm_invoke", prepare_litellm_invoke)

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

    class _FakeSettleRepo(FakeBudgetRepository):
        pass

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
    assert budget.releases == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_settle_usage_releases_token_estimate_without_releasing_request_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        platform_budget_preflight=PlatformBudgetPreflightState(
            reservations=[
                BudgetReservation(
                    target_kind="tenant",
                    target_id=str(team_id),
                    period="monthly",
                    budget_model_name="gpt-4o-mini",
                    reserved_requests=1,
                    reserved_tokens=50,
                )
            ]
        ),
    )
    budget = CommitRecordingBudgetService()

    monkeypatch.setattr(proxy_response_adapter, "get_session_context", lambda: _DummySessionCM())
    monkeypatch.setattr(proxy_response_adapter, "BudgetRepository", FakeBudgetRepository)

    await settle_usage(
        ctx,
        budget,
        tokens=7,
        cost=Decimal("0.02"),
        requests=1,
    )

    assert (
        "tenant",
        str(team_id),
        "monthly",
        "gpt-4o-mini",
        0,
        50,
    ) in budget.releases
    assert ctx.platform_budget_preflight is not None
    assert ctx.platform_budget_preflight.token_reservations_released is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_settle_usage_keeps_token_estimate_when_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        platform_budget_preflight=PlatformBudgetPreflightState(
            reservations=[
                BudgetReservation(
                    target_kind="tenant",
                    target_id=str(team_id),
                    period="monthly",
                    budget_model_name="gpt-4o-mini",
                    reserved_requests=1,
                    reserved_tokens=50,
                )
            ]
        ),
    )
    budget = FailingCommitBudgetService()

    monkeypatch.setattr(proxy_response_adapter, "get_session_context", lambda: _DummySessionCM())
    monkeypatch.setattr(proxy_response_adapter, "BudgetRepository", FakeBudgetRepository)

    await settle_usage(
        ctx,
        budget,
        tokens=7,
        cost=Decimal("0.02"),
        requests=1,
    )

    assert budget.releases == []
