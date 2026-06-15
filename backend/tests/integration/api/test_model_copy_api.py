"""POST /api/v1/gateway/models/copy-to-team 集成测试。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest

from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService


@pytest.mark.integration
class TestModelCopyApi:
    @pytest.mark.asyncio
    async def test_copy_personal_model_subset_via_api(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        target_team = await TeamService(db_session).create_team(
            name="api-model-copy-target",
            slug=f"api-mcopy-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await db_session.commit()

        r_cred = await dev_client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "openai",
                "name": f"mc-src-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-model-copy-src",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        r_model = await dev_client.post(
            "/api/v1/gateway/my-models",
            headers=auth_headers,
            json={
                "display_name": "Copy Me",
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "credential_id": cred_id,
                "model_types": ["text"],
            },
        )
        assert r_model.status_code == 201, r_model.text
        model_id = r_model.json()[0]["id"]

        r_dest_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{target_team.id}/credentials",
            headers={**auth_headers, "X-Team-Id": str(target_team.id)},
            json={
                "provider": "openai",
                "name": f"mc-dest-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-model-copy-dest",
            },
        )
        assert r_dest_cred.status_code == 201, r_dest_cred.text
        dest_cred_id = r_dest_cred.json()["id"]

        r_copy = await dev_client.post(
            "/api/v1/gateway/models/copy-to-team",
            headers=auth_headers,
            json={
                "model_ids": [model_id],
                "destination_team_id": str(target_team.id),
                "credential_plans": [
                    {
                        "source_credential_id": cred_id,
                        "mode": "existing",
                        "destination_credential_id": dest_cred_id,
                    }
                ],
            },
        )
        assert r_copy.status_code == 201, r_copy.text
        body = r_copy.json()
        assert len(body["succeeded"]) == 1
        assert body["failed"] == []

        r_models = await dev_client.get(
            f"/api/v1/gateway/teams/{target_team.id}/models",
            headers={**auth_headers, "X-Team-Id": str(target_team.id)},
        )
        assert r_models.status_code == 200, r_models.text
        names = {row["name"] for row in r_models.json()["items"]}
        assert body["succeeded"][0]["name"] in names

    @pytest.mark.asyncio
    async def test_copy_other_user_model_returns_failed_item(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        other = User(
            email=f"mc_other_{uuid.uuid4()}@example.com",
            hashed_password="hashed_password",
            name="MC Other",
        )
        db_session.add(other)
        await db_session.flush()

        source_team = await TeamService(db_session).create_team(
            name="api-mcopy-deny-src",
            slug=f"api-mc-deny-{uuid.uuid4().hex[:8]}",
            owner_user_id=other.id,
        )
        target_team = await TeamService(db_session).create_team(
            name="api-mcopy-deny-dst",
            slug=f"api-mc-deny-d-{uuid.uuid4().hex[:8]}",
            owner_user_id=test_user.id,
        )
        await TeamService(db_session).add_member(source_team.id, test_user.id, role="admin")
        await db_session.commit()

        from domains.identity.application import UserUseCase

        other_token = await UserUseCase(db_session).create_token(other)
        other_headers = {"Authorization": f"Bearer {other_token.access_token}"}

        r_cred = await dev_client.post(
            f"/api/v1/gateway/teams/{source_team.id}/credentials",
            headers={**other_headers, "X-Team-Id": str(source_team.id)},
            json={
                "provider": "openai",
                "name": f"private-{uuid.uuid4().hex[:6]}",
                "api_key": "sk-private-model-copy",
            },
        )
        assert r_cred.status_code == 201, r_cred.text
        cred_id = r_cred.json()["id"]

        r_model = await dev_client.post(
            f"/api/v1/gateway/teams/{source_team.id}/models",
            headers={**other_headers, "X-Team-Id": str(source_team.id)},
            json={
                "name": "private-alias",
                "capability": "chat",
                "real_model": "gpt-4o-mini",
                "credential_id": cred_id,
                "provider": "openai",
            },
        )
        assert r_model.status_code == 201, r_model.text
        model_id = r_model.json()["id"]

        r_copy = await dev_client.post(
            "/api/v1/gateway/models/copy-to-team",
            headers=auth_headers,
            json={
                "model_ids": [model_id],
                "destination_team_id": str(target_team.id),
                "credential_plans": [
                    {
                        "source_credential_id": cred_id,
                        "mode": "copy_credential",
                    }
                ],
            },
        )
        assert r_copy.status_code == 200, r_copy.text
        body = r_copy.json()
        assert body["succeeded"] == []
        assert len(body["failed"]) == 1
        assert body["failed"][0]["reason"] == "credential not found"
