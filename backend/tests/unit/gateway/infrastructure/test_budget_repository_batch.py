"""BudgetRepository.get_many_by_plan 批量查询。"""

from __future__ import annotations

from decimal import Decimal
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.domain.proxy_policy import BudgetCheckQuery
from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository


@pytest.mark.asyncio
async def test_get_many_by_plan_single_query(db_session: AsyncSession) -> None:
    team_id = uuid.uuid4()
    model_name = "gpt-test-batch"
    budget = GatewayBudget(
        target_kind="team",
        target_id=team_id,
        period="monthly",
        model_name=model_name,
        limit_usd=Decimal("10"),
    )
    db_session.add(budget)
    await db_session.flush()

    repo = BudgetRepository(db_session)
    plan = (
        BudgetCheckQuery(
            target_kind="team",
            target_id=team_id,
            period="monthly",
            model_name=model_name,
        ),
        BudgetCheckQuery(
            target_kind="team",
            target_id=team_id,
            period="monthly",
            model_name=None,
        ),
    )
    rows = await repo.get_many_by_plan(plan)
    assert (
        budget.target_kind,
        budget.target_id,
        budget.period,
        budget.model_name,
        budget.credential_id,
        budget.tenant_id,
    ) in rows
    assert len(rows) == 1
