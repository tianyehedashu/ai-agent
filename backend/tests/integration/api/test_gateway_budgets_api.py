"""
Gateway 预算管理 API 集成测试（GET/PUT/DELETE /budgets）。
"""

from __future__ import annotations

from decimal import Decimal
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


@pytest.mark.integration
class TestGatewayBudgetsApi:
    @pytest.mark.asyncio
    async def test_admin_lists_tenant_budget(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        budget = GatewayBudget(
            target_kind="tenant",
            target_id=team.id,
            period="monthly",
            model_name=None,
            limit_usd=Decimal("100"),
        )
        db_session.add(budget)
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/budgets",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert any(
            row["target_kind"] == "tenant" and row["target_id"] == str(team.id) for row in rows
        )

    @pytest.mark.asyncio
    async def test_delete_rejects_cross_tenant_budget(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        other_team = await TeamService(db_session).create_team(
            name="Other Budget Team",
            owner_user_id=test_user.id,
        )
        foreign_budget = GatewayBudget(
            target_kind="tenant",
            target_id=other_team.id,
            period="monthly",
            model_name=None,
            limit_usd=Decimal("50"),
        )
        db_session.add(foreign_budget)
        await db_session.commit()
        await db_session.refresh(foreign_budget)

        r = await dev_client.delete(
            f"/api/v1/gateway/teams/{team.id}/budgets/{foreign_budget.id}",
            headers=auth_headers,
        )
        assert r.status_code == 404, r.text

    @pytest.mark.asyncio
    async def test_upsert_rejects_foreign_user_target(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        outsider = User(
            email=f"budget-outsider-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed_password",
            name="Budget Outsider",
        )
        db_session.add(outsider)
        await db_session.commit()

        r = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/budgets",
            headers=auth_headers,
            json={
                "target_kind": "user",
                "target_id": str(outsider.id),
                "period": "monthly",
                "limit_usd": 10,
            },
        )
        assert r.status_code == 404, r.text

    @pytest.mark.asyncio
    async def test_upsert_tenant_budget_for_own_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)

        r = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/budgets",
            headers=auth_headers,
            json={
                "target_kind": "tenant",
                "period": "daily",
                "limit_usd": 25,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["target_kind"] == "tenant"
        assert body["target_id"] == str(team.id)
        assert body["period"] == "daily"

    @pytest.mark.asyncio
    async def test_admin_lists_user_budgets_filtered_by_model_name(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        matching = GatewayBudget(
            target_kind="user",
            target_id=test_user.id,
            tenant_id=team.id,
            period="monthly",
            model_name="gpt-4",
            limit_usd=Decimal("20"),
        )
        other = GatewayBudget(
            target_kind="user",
            target_id=test_user.id,
            tenant_id=team.id,
            period="monthly",
            model_name="claude-3",
            limit_usd=Decimal("30"),
        )
        db_session.add_all([matching, other])
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/budgets?target_kind=user&model_name=gpt-4",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["model_name"] == "gpt-4"
        assert rows[0]["target_kind"] == "user"
