"""
Gateway 管理面 /api/v1/gateway/* 集成测试（dev_client + JWT）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.application.team_service import TeamService
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.identity.infrastructure.models.user import User


@pytest.mark.integration
class TestGatewayManagementApi:
    @pytest.mark.asyncio
    async def test_list_teams_with_personal_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()

        r = await dev_client.get("/api/v1/gateway/teams", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        personal = next((t for t in data if t.get("kind") == "personal"), None)
        assert personal is not None
        assert personal.get("team_role") == "owner"

    @pytest.mark.asyncio
    async def test_get_log_detail(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        log_id = uuid.uuid4()
        now = datetime.now(UTC)
        row = GatewayRequestLog(
            id=log_id,
            created_at=now,
            team_id=team.id,
            user_id=test_user.id,
            vkey_id=None,
            capability="chat",
            route_name=None,
            real_model="gpt-4",
            provider="openai",
            status="success",
            input_tokens=10,
            output_tokens=5,
            cached_tokens=0,
            cost_usd=Decimal("0.001"),
            latency_ms=100,
            cache_hit=False,
            fallback_chain=[],
            request_id="req-test",
        )
        db_session.add(row)
        await db_session.commit()

        headers = {**auth_headers, "X-Team-Id": str(team.id)}
        r = await dev_client.get(f"/api/v1/gateway/logs/{log_id}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == str(log_id)
        assert body["team_id"] == str(team.id)
