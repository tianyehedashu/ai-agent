"""
Gateway 定价目录 /api/v1/gateway/teams/{id}/pricing/* 集成测试。
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.application.management.write_modules import GatewayManagementWriteService
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


@pytest.mark.integration
class TestGatewayPricingApi:
    @pytest.mark.asyncio
    async def test_list_downstream_includes_model_and_credential_names(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        cred_name = f"pricing-cred-{uuid.uuid4().hex[:8]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-pricing-int-test-key-12345678",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cid = r_cred.json()["id"]

        model_name = f"pricing-vm-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cid,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text
        mid = r_model.json()["id"]

        r_sync = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/pricing/downstream/sync",
            headers=headers,
            params={"scope": "tenant"},
        )
        assert r_sync.status_code == 200, r_sync.text

        r_list = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/pricing/downstream",
            headers=headers,
            params={"scope": "tenant", "currency": "CNY"},
        )
        assert r_list.status_code == 200, r_list.text
        rows = r_list.json()
        matched = next((row for row in rows if row.get("gateway_model_id") == mid), None)
        assert matched is not None, rows
        assert matched["model_name"] == model_name
        assert matched["provider"] == "openai"
        assert matched["credential_name"] == cred_name
        assert matched["credential_id"] == cid
        assert matched["registry_kind"] == "team"

    @pytest.mark.asyncio
    async def test_list_my_prices_includes_credential_name(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        await db_session.commit()
        headers = auth_headers
        cred_name = f"myprice-cred-{uuid.uuid4().hex[:8]}"
        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/credentials",
            headers=headers,
            json={
                "provider": "openai",
                "name": cred_name,
                "api_key": "sk-myprice-int-test-key-12345678",
                "scope": "team",
            },
        )
        assert r_cred.status_code == 201, r_cred.text

        model_name = f"myprice-vm-{uuid.uuid4().hex[:6]}"
        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/models",
            headers=headers,
            json={
                "name": model_name,
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": r_cred.json()["id"],
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text
        mid = r_model.json()["id"]

        writes = GatewayManagementWriteService(db_session)
        await writes.upsert_upstream_pricing(
            provider="openai",
            upstream_model="gpt-4o-mini",
            capability="chat",
            currency="CNY",
            amount_per_million={"input": 1, "output": 2},
        )
        await db_session.commit()

        r_sync = await dev_client.post(
            f"/api/v1/gateway/teams/{team.id}/pricing/downstream/sync",
            headers=headers,
            params={"scope": "tenant"},
        )
        assert r_sync.status_code == 200, r_sync.text

        r_my = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/pricing/my",
            headers=headers,
            params={"currency": "CNY"},
        )
        assert r_my.status_code == 200, r_my.text
        rows = r_my.json()
        matched = next((row for row in rows if row.get("gateway_model_id") == mid), None)
        assert matched is not None, rows
        assert matched["credential_name"] == cred_name
        assert matched["provider"] == "openai"
