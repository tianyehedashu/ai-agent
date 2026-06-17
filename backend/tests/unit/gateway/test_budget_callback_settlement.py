"""budget_callback_settlement 幂等与 delta。"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.budget_callback_settlement import (
    commit_budget_from_callback,
    record_proxy_cost_commit,
)


@pytest.mark.asyncio
async def test_commit_skips_when_no_request_id() -> None:
    await commit_budget_from_callback(
        metadata={"gateway_team_id": "00000000-0000-0000-0000-000000000001"},
        request_id=None,
        cost_usd=Decimal("1"),
        total_tokens=10,
        budget_model="m",
    )


@pytest.mark.asyncio
async def test_commit_defer_applies_full_cost() -> None:
    team_id = "00000000-0000-0000-0000-000000000099"
    team_uuid = uuid.UUID(team_id)
    metadata = {
        "gateway_team_id": team_id,
        "gateway_defer_cost_settlement": True,
    }
    mock_client = AsyncMock()
    mock_client.set = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value=None)
    mock_budget = AsyncMock()
    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    from types import SimpleNamespace

    budget_row = SimpleNamespace(
        id=uuid.uuid4(),
        target_kind="tenant",
        target_id=team_uuid,
        period="daily",
        model_name=None,
        limit_usd=Decimal("100"),
        limit_tokens=None,
        limit_requests=None,
        credential_id=None,
        tenant_id=None,
        period_timezone="UTC",
        period_reset_minutes=0,
        period_reset_day=1,
    )

    async def _get_many_by_plan(plan: object) -> dict:
        out = {}
        for query in plan:  # type: ignore[union-attr]
            if query.target_kind == "tenant" and query.target_id == team_uuid:
                out[
                    (
                        query.target_kind,
                        query.target_id,
                        query.period,
                        query.model_name,
                        query.credential_id,
                        query.tenant_id,
                    )
                ] = budget_row
        return out

    with (
        patch(
            "domains.gateway.application.budget_callback_settlement.get_redis_client",
            return_value=mock_client,
        ),
        patch(
            "domains.gateway.application.budget_callback_settlement.BudgetService",
            return_value=mock_budget,
        ),
        patch("domains.gateway.application.budget_callback_settlement.get_session_context", return_value=mock_cm),
        patch(
            "domains.gateway.application.budget_callback_settlement.BudgetRepository",
        ) as mock_repo_cls,
    ):
        mock_repo_cls.return_value.get_many_by_plan = AsyncMock(side_effect=_get_many_by_plan)
        mock_repo_cls.return_value.get_for = AsyncMock(return_value=budget_row)
        mock_repo_cls.return_value.settle_usage = AsyncMock()
        await commit_budget_from_callback(
            metadata=metadata,
            request_id="req-1",
            cost_usd=Decimal("0.02"),
            total_tokens=100,
            budget_model="team/model",
        )
    assert mock_budget.commit.await_count >= 1
    call = mock_budget.commit.await_args_list[0].kwargs
    assert call["delta_cost"] == Decimal("0.02")


@pytest.mark.asyncio
async def test_commit_non_stream_delta_zero_skips_budget() -> None:
    mock_client = AsyncMock()
    mock_client.set = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value=b"0.02")
    mock_budget = AsyncMock()
    with (
        patch(
            "domains.gateway.application.budget_callback_settlement.get_redis_client",
            return_value=mock_client,
        ),
        patch(
            "domains.gateway.application.budget_callback_settlement.BudgetService",
            return_value=mock_budget,
        ),
    ):
        await commit_budget_from_callback(
            metadata={
                "gateway_team_id": "00000000-0000-0000-0000-000000000099",
            },
            request_id="req-2",
            cost_usd=Decimal("0.02"),
            total_tokens=50,
            budget_model=None,
        )
    mock_budget.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_proxy_cost_commit() -> None:
    mock_client = AsyncMock()
    with patch(
        "domains.gateway.application.budget_callback_settlement.get_redis_client",
        return_value=mock_client,
    ):
        await record_proxy_cost_commit("req-x", Decimal("0.01"))
    mock_client.set.assert_awaited_once()


def _dedup_session_patches(mock_client: AsyncMock, captured: dict) -> tuple:
    """复用：mock Redis + PG 会话 + 平台预算累加，捕获 callback 实际补差。"""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    async def _fake_commit(_budget: object, **kwargs: object) -> None:
        captured.update(kwargs)

    return (
        patch(
            "domains.gateway.application.budget_callback_settlement.get_redis_client",
            return_value=mock_client,
        ),
        patch(
            "domains.gateway.application.budget_callback_settlement.BudgetService",
            return_value=AsyncMock(),
        ),
        patch(
            "domains.gateway.application.budget_callback_settlement.commit_cached_platform_budgets",
            side_effect=_fake_commit,
        ),
        patch(
            "domains.gateway.application.budget_callback_settlement.get_session_context",
            return_value=mock_cm,
        ),
        patch(
            "domains.gateway.application.budget_callback_settlement.BudgetRepository",
        ),
    )


@pytest.mark.asyncio
async def test_defer_dedups_proxy_tokens_fully() -> None:
    """defer 流式：proxy 已记全部 token，callback 不得重复累加 token（回归 token 双计）。"""
    mock_client = AsyncMock()
    mock_client.set = AsyncMock(return_value=True)
    # get 顺序：proxy_cost(None) → proxy_tokens(b"100")
    mock_client.get = AsyncMock(side_effect=[None, b"100"])
    captured: dict = {}

    redis_p, budget_p, commit_p, session_p, repo_p = _dedup_session_patches(mock_client, captured)
    with redis_p, budget_p, commit_p, session_p, repo_p as repo_cls:
        repo_cls.return_value.get_for = AsyncMock(return_value=None)
        await commit_budget_from_callback(
            metadata={
                "gateway_team_id": "00000000-0000-0000-0000-000000000099",
                "gateway_defer_cost_settlement": True,
            },
            request_id="req-defer-tok",
            cost_usd=Decimal("0.02"),
            total_tokens=100,
            budget_model=None,
        )
    assert captured["delta_tokens"] == 0
    assert captured["delta_cost"] == Decimal("0.02")


@pytest.mark.asyncio
async def test_defer_dedups_proxy_tokens_partial() -> None:
    """defer 流式：callback 仅补 proxy 未记的 token 增量。"""
    mock_client = AsyncMock()
    mock_client.set = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(side_effect=[None, b"60"])
    captured: dict = {}

    redis_p, budget_p, commit_p, session_p, repo_p = _dedup_session_patches(mock_client, captured)
    with redis_p, budget_p, commit_p, session_p, repo_p as repo_cls:
        repo_cls.return_value.get_for = AsyncMock(return_value=None)
        await commit_budget_from_callback(
            metadata={
                "gateway_team_id": "00000000-0000-0000-0000-000000000099",
                "gateway_defer_cost_settlement": True,
            },
            request_id="req-defer-tok2",
            cost_usd=Decimal("0"),
            total_tokens=100,
            budget_model=None,
        )
    assert captured["delta_tokens"] == 40


@pytest.mark.asyncio
async def test_non_stream_proxy_cost_without_tokens_no_double_count() -> None:
    """proxy 已结算但未单独记 token（旧 proxy 仅记 cost / token 写失败）：

    callback 必须按「proxy 已结算」视为 token 已计入，仅补 cost 差额，不重复累加 token。
    """
    mock_client = AsyncMock()
    mock_client.set = AsyncMock(return_value=True)
    # get 顺序：proxy_cost(b"0.02") → proxy_tokens(None)
    mock_client.get = AsyncMock(side_effect=[b"0.02", None])
    captured: dict = {}

    redis_p, budget_p, commit_p, session_p, repo_p = _dedup_session_patches(mock_client, captured)
    with redis_p, budget_p, commit_p, session_p, repo_p as repo_cls:
        repo_cls.return_value.get_for = AsyncMock(return_value=None)
        await commit_budget_from_callback(
            metadata={"gateway_team_id": "00000000-0000-0000-0000-000000000099"},
            request_id="req-cost-no-tok",
            cost_usd=Decimal("0.05"),
            total_tokens=50,
            budget_model=None,
        )
    assert captured["delta_tokens"] == 0
    assert captured["delta_cost"] == Decimal("0.03")
