"""POST /api/v1/gateway/credentials/copy-with-models 集成测试。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest

from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


@pytest.mark.integration
class TestCredentialCopyApi:
    @pytest.mark.asyncio
    async def test_copy_personal_to_team_via_api(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        target_team = await TeamService(db_session).create_team(
            name="api-copy-target",
            slug=f"api-copy-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"copy-src-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-copy-with-models-test-key",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        r_copy = await dev_client.post(
            "/api/v1/gateway/credentials/copy-with-models",
            headers=auth_headers,
            json={
                "credential_ids": [cred_id],
                "source": {"kind": "personal"},
                "destination": {"kind": "team", "team_id": str(target_team.id)},
            },
        )
        assert r_copy.status_code == 201, r_copy.text
        body = r_copy.json()
        assert len(body["succeeded"]) == 1
        assert body["succeeded"][0]["source_credential_id"] == cred_id
        assert body["failed"] == []

        r_team_creds = await dev_client.get(
            f"/api/v1/gateway/teams/{target_team.id}/credentials",
            headers={**auth_headers, "X-Team-Id": str(target_team.id)},
        )
        assert r_team_creds.status_code == 200, r_team_creds.text
        names = {row["name"] for row in r_team_creds.json()}
        assert body["succeeded"][0]["new_credential"]["name"] in names

    @pytest.mark.asyncio
    async def test_copy_personal_to_personal_returns_400(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"copy-invalid-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-copy-invalid-endpoint",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        r_copy = await dev_client.post(
            "/api/v1/gateway/credentials/copy-with-models",
            headers=auth_headers,
            json={
                "credential_ids": [cred_id],
                "source": {"kind": "personal"},
                "destination": {"kind": "personal"},
            },
        )
        assert r_copy.status_code == 400, r_copy.text
        assert r_copy.json().get("code") == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_copy_other_user_credential_returns_failed_item(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        other_user = User(
            email=f"copy_other_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="Copy Other User",
        )
        db_session.add(other_user)
        await db_session.flush()

        target_team = await TeamService(db_session).create_team(
            name="api-copy-deny-target",
            slug=f"api-deny-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await TeamService(db_session).add_member(target_team.id, other_user.id, role="member")
        await db_session.commit()

        from domains.identity.application import UserUseCase

        other_token = await UserUseCase(db_session).create_token(other_user)
        other_headers = {"Authorization": f"Bearer {other_token.access_token}"}

        r_victim_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"victim-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-victim-copy-key",
            },
        )
        assert r_victim_cred.status_code == 201, r_victim_cred.text
        victim_cred_id = r_victim_cred.json()["id"]

        r_copy = await dev_client.post(
            "/api/v1/gateway/credentials/copy-with-models",
            headers=other_headers,
            json={
                "credential_ids": [victim_cred_id],
                "source": {"kind": "personal"},
                "destination": {"kind": "team", "team_id": str(target_team.id)},
            },
        )
        assert r_copy.status_code == 201, r_copy.text
        body = r_copy.json()
        assert body["succeeded"] == []
        assert len(body["failed"]) == 1
        assert body["failed"][0]["credential_id"] == victim_cred_id
        assert body["failed"][0]["reason"] == "credential not found"
