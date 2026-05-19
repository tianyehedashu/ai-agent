"""budget_callback_settlement 幂等与 delta。"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

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
    with (
        patch(
            "domains.gateway.application.budget_callback_settlement.get_redis_client",
            return_value=mock_client,
        ),
        patch(
            "domains.gateway.application.budget_callback_settlement.BudgetService",
            return_value=mock_budget,
        ),
        patch("libs.db.database.get_session_context", return_value=mock_cm),
        patch(
            "domains.gateway.infrastructure.repositories.budget_repository.BudgetRepository",
        ) as mock_repo_cls,
    ):
        mock_repo_cls.return_value.get_for = AsyncMock(return_value=None)
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
