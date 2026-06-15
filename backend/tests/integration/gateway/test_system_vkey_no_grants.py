"""system vkey 不参与 grants / dispatch 集成测试。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


@pytest.mark.integration
class TestSystemVkeyNoGrants:
    @pytest.mark.asyncio
    async def test_grants_api_rejects_system_vkey(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        from bootstrap.config import settings

        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        repo = VirtualKeyRepository(db_session)
        key_id = uuid.uuid4().hex[:16]
        record = await repo.create(
            tenant_id=team.id,
            created_by_user_id=None,
            name=f"sys-{uuid.uuid4().hex[:6]}",
            description=None,
            key_id_str=key_id,
            key_hash=key_id,
            encrypted_key=encrypt_value(
                "sk-gw-sys",
                derive_encryption_key(settings.secret_key.get_secret_value()),
            ),
            allowed_models=[],
            allowed_capabilities=["chat"],
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=False,
            guardrail_enabled=False,
            is_system=True,
            expires_at=None,
        )
        await db_session.commit()

        r = await dev_client.get(
            f"/api/v1/gateway/teams/{team.id}/keys/{record.id}/grants",
            headers=auth_headers,
        )
        assert r.status_code == 403, r.text
