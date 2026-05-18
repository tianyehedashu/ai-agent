"""CredentialUpstreamCatalogService 单元测试（假 Port，真实 DB 会话）。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.credential_upstream_catalog import (
    CredentialUpstreamCatalogService,
)
from domains.gateway.application.management.ports import RawUpstreamListResult
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.identity.infrastructure.models.user import User
from libs.crypto import derive_encryption_key, encrypt_value


@pytest.mark.asyncio
async def test_probe_user_anthropic_no_http(db_session, test_user: User) -> None:
    port = AsyncMock()
    key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    row = await cred_repo.create(
        scope="user",
        scope_id=test_user.id,
        provider="anthropic",
        name="u-anthropic",
        api_key_encrypted=encrypt_value("sk-ant-test", key),
        api_base=None,
        extra=None,
    )
    await db_session.commit()

    svc = CredentialUpstreamCatalogService(db_session, port=port)
    result = await svc.probe_user_credential(user_id=test_user.id, credential_id=row.id)
    assert result.support == "unsupported"
    assert result.upstream == "none"
    assert result.items == ()
    assert result.message
    port.fetch_models.assert_not_called()


@pytest.mark.asyncio
async def test_probe_user_decrypt_failure_no_upstream_call(db_session, test_user: User) -> None:
    port = AsyncMock()
    cred_repo = ProviderCredentialRepository(db_session)
    row = await cred_repo.create(
        scope="user",
        scope_id=test_user.id,
        provider="openai",
        name="u-bad-cipher",
        api_key_encrypted="not-a-valid-fernet-payload",
        api_base=None,
        extra=None,
    )
    await db_session.commit()

    svc = CredentialUpstreamCatalogService(db_session, port=port)
    result = await svc.probe_user_credential(user_id=test_user.id, credential_id=row.id)
    assert result.support == "error"
    assert result.message
    assert "解密" in (result.message or "")
    port.fetch_models.assert_not_called()


@pytest.mark.asyncio
async def test_probe_user_openai_uses_port(db_session, test_user: User) -> None:
    port = AsyncMock()
    port.fetch_models = AsyncMock(
        return_value=RawUpstreamListResult(
            ok=True,
            http_status=200,
            items=(("gpt-4o-mini", "openai"),),
            error_message=None,
        )
    )
    key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    row = await cred_repo.create(
        scope="user",
        scope_id=test_user.id,
        provider="openai",
        name="u-openai",
        api_key_encrypted=encrypt_value("sk-test-openai", key),
        api_base=None,
        extra=None,
    )
    await db_session.commit()

    svc = CredentialUpstreamCatalogService(db_session, port=port)
    result = await svc.probe_user_credential(user_id=test_user.id, credential_id=row.id)
    assert result.support == "full"
    assert len(result.items) == 1
    assert result.items[0].id == "gpt-4o-mini"
    port.fetch_models.assert_awaited_once()
    call_kw = port.fetch_models.await_args.kwargs
    assert "api.openai.com" in call_kw["list_url"]


@pytest.mark.asyncio
async def test_probe_user_inactive_returns_error(db_session, test_user: User) -> None:
    port = AsyncMock()
    key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    row = await cred_repo.create(
        scope="user",
        scope_id=test_user.id,
        provider="openai",
        name="u-inactive",
        api_key_encrypted=encrypt_value("sk-x", key),
        api_base=None,
        extra=None,
        is_active=False,
    )
    await db_session.commit()

    svc = CredentialUpstreamCatalogService(db_session, port=port)
    result = await svc.probe_user_credential(user_id=test_user.id, credential_id=row.id)
    assert result.support == "error"
    assert "禁用" in (result.message or "")
    port.fetch_models.assert_not_called()
