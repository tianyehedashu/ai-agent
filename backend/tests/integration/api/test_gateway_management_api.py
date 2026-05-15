"""
Gateway 管理面 /api/v1/gateway/* 集成测试（dev_client + JWT）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


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
        cred_id = uuid.uuid4()
        now = datetime.now(UTC)
        row = GatewayRequestLog(
            id=log_id,
            created_at=now,
            team_id=team.id,
            user_id=test_user.id,
            vkey_id=None,
            credential_id=cred_id,
            credential_name_snapshot="team-openai",
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
            ttfb_ms=42,
            cache_hit=False,
            fallback_chain=[],
            request_id="req-test",
            prompt_hash="phash",
            prompt_redacted={"messages_preview": [{"role": "user", "content": "hi"}]},
            response_summary={"text": "hello"},
            metadata_extra={"foo": "bar"},
        )
        db_session.add(row)
        await db_session.commit()

        headers = {**auth_headers, "X-Team-Id": str(team.id)}
        r = await dev_client.get(f"/api/v1/gateway/logs/{log_id}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == str(log_id)
        assert body["team_id"] == str(team.id)
        assert body["credential_id"] == str(cred_id)
        assert body["credential_name_snapshot"] == "team-openai"
        assert body["ttfb_ms"] == 42
        assert body["prompt_hash"] == "phash"
        assert body["prompt_redacted"]["messages_preview"][0]["role"] == "user"
        assert body["response_summary"]["text"] == "hello"
        assert body["metadata_extra"] == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_user_aggregation_uses_current_user_not_selected_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        personal = await TeamService(db_session).ensure_personal_team(test_user.id)
        shared = await TeamService(db_session).create_team(
            name="Shared Stats Team",
            owner_user_id=test_user.id,
        )
        now = datetime.now(UTC)
        personal_log_id = uuid.uuid4()
        shared_log_id = uuid.uuid4()
        other_log_id = uuid.uuid4()
        db_session.add_all(
            [
                GatewayRequestLog(
                    id=personal_log_id,
                    created_at=now,
                    team_id=personal.id,
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
                    request_id="req-personal",
                ),
                GatewayRequestLog(
                    id=shared_log_id,
                    created_at=now,
                    team_id=shared.id,
                    user_id=test_user.id,
                    vkey_id=None,
                    capability="chat",
                    route_name=None,
                    real_model="gpt-4",
                    provider="openai",
                    status="success",
                    input_tokens=3,
                    output_tokens=2,
                    cached_tokens=0,
                    cost_usd=Decimal("0.001"),
                    latency_ms=120,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id="req-shared",
                ),
                GatewayRequestLog(
                    id=other_log_id,
                    created_at=now,
                    team_id=shared.id,
                    user_id=uuid.uuid4(),
                    vkey_id=None,
                    capability="chat",
                    route_name=None,
                    real_model="gpt-4",
                    provider="openai",
                    status="success",
                    input_tokens=100,
                    output_tokens=50,
                    cached_tokens=0,
                    cost_usd=Decimal("1"),
                    latency_ms=150,
                    cache_hit=False,
                    fallback_chain=[],
                    request_id="req-other",
                ),
            ]
        )
        await db_session.commit()

        headers = {**auth_headers, "X-Team-Id": str(shared.id)}
        logs = await dev_client.get(
            "/api/v1/gateway/logs?usage_aggregation=user&page_size=10",
            headers=headers,
        )
        assert logs.status_code == 200, logs.text
        ids = {item["id"] for item in logs.json()["items"]}
        assert str(personal_log_id) in ids
        assert str(shared_log_id) in ids
        assert str(other_log_id) not in ids

        detail = await dev_client.get(
            f"/api/v1/gateway/logs/{personal_log_id}?usage_aggregation=user",
            headers=headers,
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["id"] == str(personal_log_id)

        summary = await dev_client.get(
            "/api/v1/gateway/dashboard/summary?usage_aggregation=user&days=1",
            headers=headers,
        )
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body["total_requests"] == 2
        assert body["total_input_tokens"] == 13
        assert body["total_output_tokens"] == 7

    @pytest.mark.asyncio
    async def test_list_model_presets_filter_by_provider(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = {**auth_headers, "X-Team-Id": str(team.id)}
        r_all = await dev_client.get("/api/v1/gateway/models/presets", headers=headers)
        assert r_all.status_code == 200, r_all.text
        all_presets = r_all.json()
        if not all_presets:
            pytest.skip("no catalog presets in environment")
        p0 = str(all_presets[0]["provider"])
        r_f = await dev_client.get(
            "/api/v1/gateway/models/presets",
            params={"provider": p0},
            headers=headers,
        )
        assert r_f.status_code == 200, r_f.text
        filtered = r_f.json()
        assert all(str(x["provider"]) == p0 for x in filtered)
        assert len(filtered) <= len(all_presets)

    @pytest.mark.asyncio
    async def test_get_managed_credential_and_list_models_by_credential_id(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = {**auth_headers, "X-Team-Id": str(team.id)}
        name = f"int-test-cred-{uuid.uuid4().hex[:8]}"
        r_create = await dev_client.post(
            "/api/v1/gateway/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": name,
                "api_key": "sk-int-test-key-for-gateway-123456",
                "api_base": None,
                "scope": "team",
            },
        )
        assert r_create.status_code == 201, r_create.text
        cred_body = r_create.json()
        cid = cred_body["id"]
        assert "api_key_masked" in cred_body
        assert "sk-int-test-key-for-gateway-123456" not in cred_body["api_key_masked"]

        r_get = await dev_client.get(f"/api/v1/gateway/credentials/{cid}", headers=headers)
        assert r_get.status_code == 200, r_get.text
        got = r_get.json()
        assert got["id"] == cid
        assert got["name"] == name

        r_models = await dev_client.get(
            "/api/v1/gateway/models",
            headers=headers,
            params={"credential_id": cid},
        )
        assert r_models.status_code == 200, r_models.text
        models = r_models.json()
        assert all(m["credential_id"] == cid for m in models)
