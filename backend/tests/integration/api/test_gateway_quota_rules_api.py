"""
Gateway 配额规则统一 API 集成测试。
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
class TestGatewayQuotaRulesApi:
    @pytest.mark.asyncio
    async def test_list_quota_rules_includes_platform_budget(
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
            limit_usd=Decimal("50"),
        )
        db_session.add(budget)
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/quota-rules",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert any(
            row["key"]["layer"] == "platform" and row["source_ref"]["budget_id"] is not None
            for row in rows
        )

    @pytest.mark.asyncio
    async def test_batch_upsert_platform_quota(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        r = await dev_client.put(
            f"/api/v1/gateway/teams/{team.id}/quota-rules/batch",
            headers=auth_headers,
            json={
                "rules": [
                    {
                        "layer": "platform",
                        "target_kind": "tenant",
                        "period": "daily",
                        "limit_usd": "25.00",
                    }
                ]
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["succeeded"]) == 1
        assert body["failed"] == []

        listed = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/quota-rules?layer=platform",
            headers=auth_headers,
        )
        assert listed.status_code == 200
        assert any(row["key"]["period"] == "daily" for row in listed.json())
