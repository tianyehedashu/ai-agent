"""凭据 ReadModel 映射与 presentation 响应组装。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.credential_read_mappers import (
    credential_from_orm,
    ensure_credential_read_model,
)
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.presentation.credential_response import (
    build_credential_response,
    build_credential_summary_response,
)
from libs.crypto import derive_encryption_key, encrypt_value
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


@pytest.mark.asyncio
async def test_ensure_credential_read_model_from_system_orm(db_session) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    row = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-map-{uuid.uuid4().hex[:8]}",
        api_key_encrypted=encrypt_value("sk-system-map-test-key", encryption_key),
        api_base="https://api.openai.com/v1",
    )
    await db_session.flush()

    read_model = ensure_credential_read_model(row)
    assert read_model.scope == "system"
    assert read_model.tenant_id is None
    assert read_model.visibility == row.visibility


@pytest.mark.asyncio
async def test_create_system_credential_write_returns_read_model(db_session) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    writes = GatewayManagementWriteService(db_session)
    read_model = await writes.create_system_credential(
        is_platform_admin=True,
        provider="openai",
        name=f"sys-write-{uuid.uuid4().hex[:8]}",
        api_key_encrypted=encrypt_value("sk-system-write-test-key", encryption_key),
        api_base="https://api.openai.com/v1",
        api_bases=None,
        profile_id=None,
        extra=None,
    )
    assert read_model.scope == "system"
    assert read_model.tenant_id is None
    assert read_model.provider == "openai"


@pytest.mark.asyncio
async def test_build_credential_response_from_read_model(db_session) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    row = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-resp-{uuid.uuid4().hex[:8]}",
        api_key_encrypted=encrypt_value("sk-system-response-test-key", encryption_key),
        api_base="https://api.openai.com/v1",
    )
    await db_session.flush()
    read_model = ensure_credential_read_model(row)

    resp = build_credential_response(read_model, encryption_key=encryption_key)
    assert resp.scope == "system"
    assert resp.tenant_id is None
    assert resp.name == row.name
    assert resp.api_key_masked == "sk-s…-key"
    assert resp.visibility == row.visibility


@pytest.mark.asyncio
async def test_build_credential_response_uses_prefilled_masked_without_decrypt(
    db_session,
) -> None:
    """read model 已含 api_key_masked 时 build 不再调用 decrypt。"""
    from datetime import UTC, datetime
    from unittest.mock import patch

    from domains.gateway.application.management.credential_read_model import CredentialReadModel

    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_id = uuid.uuid4()
    read_model = CredentialReadModel(
        id=cred_id,
        tenant_id=uuid.uuid4(),
        scope="team",
        scope_id=None,
        provider="openai",
        name="prefilled-mask",
        api_base=None,
        extra=None,
        is_active=True,
        created_at=datetime.now(UTC),
        api_key_encrypted="encrypted-placeholder",
        visibility=None,
        api_key_masked="sk-p…fill",
    )

    with patch(
        "domains.gateway.presentation.credential_response.decrypt_value",
    ) as decrypt_mock:
        resp = build_credential_response(read_model, encryption_key=encryption_key)

    decrypt_mock.assert_not_called()
    assert resp.api_key_masked == "sk-p…fill"


@pytest.mark.asyncio
async def test_build_credential_summary_response(db_session, test_user) -> None:
    from domains.tenancy.application.team_service import TeamService

    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    row = await create_tenant_test_credential(
        db_session,
        team.id,
        name=f"team-sum-{uuid.uuid4().hex[:8]}",
    )
    read_model = credential_from_orm(row)

    summary = build_credential_summary_response(read_model)
    assert summary.scope == "team"
    assert summary.id == row.id
    assert summary.is_config_managed is False
