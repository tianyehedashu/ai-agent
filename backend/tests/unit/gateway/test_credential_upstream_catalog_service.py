"""CredentialUpstreamCatalogService 单元测试（假 Port，真实 DB 会话）。"""

from __future__ import annotations

from unittest.mock import AsyncMock
import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.credential_upstream_catalog import (
    CredentialUpstreamCatalogService,
)
from domains.gateway.application.management.ports import RawUpstreamListResult
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


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


@pytest.mark.asyncio
async def test_probe_managed_openai_uses_port(db_session, test_user: User) -> None:
    port = AsyncMock()
    port.fetch_models = AsyncMock(
        return_value=RawUpstreamListResult(
            ok=True,
            http_status=200,
            items=(("gpt-4o-mini", "openai"),),
            error_message=None,
        )
    )
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    row = await create_tenant_test_credential(
        db_session, team.id, name="team-openai", provider="openai"
    )
    await db_session.commit()

    svc = CredentialUpstreamCatalogService(db_session, port=port)
    result = await svc.probe_managed_credential(
        tenant_id=team.id,
        is_platform_admin=False,
        credential_id=row.id,
    )
    assert result.support == "full"
    assert result.items[0].id == "gpt-4o-mini"
    port.fetch_models.assert_awaited_once()


@pytest.mark.asyncio
async def test_batch_import_team_duplicate_fails(db_session, test_user: User) -> None:
    port = AsyncMock()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session, team.id, name="import-cred", provider="openai"
    )
    from domains.gateway.application.management.writes import GatewayManagementWriteService

    writes = GatewayManagementWriteService(db_session)
    await writes.create_gateway_model(
        tenant_id=team.id,
        name="existing-alias",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        is_platform_admin=False,
        enabled=True,
        reload_router=False,
    )
    await db_session.commit()

    svc = CredentialUpstreamCatalogService(db_session, port=port)
    created, failed = await svc.batch_import_team_models(
        tenant_id=team.id,
        is_platform_admin=False,
        credential_id=cred.id,
        provider="openai",
        capability="chat",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        enabled=True,
        items=[("gpt-4o-mini", None)],
    )
    assert created == []
    assert len(failed) == 1
    assert failed[0]["upstream_model_id"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_batch_import_team_success(db_session, test_user: User) -> None:
    port = AsyncMock()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session, team.id, name="import-cred-2", provider="openai"
    )
    await db_session.commit()

    svc = CredentialUpstreamCatalogService(db_session, port=port)
    created, failed = await svc.batch_import_team_models(
        tenant_id=team.id,
        is_platform_admin=False,
        credential_id=cred.id,
        provider="openai",
        capability="chat",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        enabled=True,
        items=[("gpt-new-model", "my-alias")],
    )
    assert failed == []
    assert len(created) == 1
    assert created[0]["upstream_model_id"] == "gpt-new-model"
    assert "gateway_model_id" in created[0]


@pytest.mark.asyncio
async def test_list_name_real_model_pairs_includes_system_gateway_models(
    db_session,
) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-pairs-{uuid.uuid4().hex[:8]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    models = GatewayModelRepository(db_session)
    await models.create_system(
        name="catalog-gpt4o",
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await db_session.commit()

    pairs = await models.list_name_real_model_pairs_for_credential(cred.id)
    assert ("catalog-gpt4o", "openai/gpt-4o-mini") in pairs


@pytest.mark.asyncio
async def test_probe_system_credential_marks_system_model_already_registered(
    db_session, test_user: User
) -> None:
    port = AsyncMock()
    port.fetch_models = AsyncMock(
        return_value=RawUpstreamListResult(
            ok=True,
            http_status=200,
            items=(("gpt-4o-mini", "openai"), ("gpt-new-only", "openai")),
            error_message=None,
        )
    )
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-probe-{uuid.uuid4().hex[:8]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await GatewayModelRepository(db_session).create_system(
        name="catalog-gpt4o-mini",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await db_session.commit()

    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    svc = CredentialUpstreamCatalogService(db_session, port=port)
    result = await svc.probe_managed_credential(
        tenant_id=team.id,
        is_platform_admin=True,
        credential_id=cred.id,
    )
    assert result.support == "full"
    by_id = {item.id: item for item in result.items}
    assert by_id["gpt-4o-mini"].already_registered is True
    assert by_id["gpt-4o-mini"].registered_names == ("catalog-gpt4o-mini",)
    assert by_id["gpt-new-only"].already_registered is False


@pytest.mark.asyncio
async def test_batch_import_system_success_writes_system_gateway_models(
    db_session, test_user: User
) -> None:
    port = AsyncMock()
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-import-{uuid.uuid4().hex[:8]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.commit()

    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    svc = CredentialUpstreamCatalogService(db_session, port=port)
    created, failed = await svc.batch_import_team_models(
        tenant_id=team.id,
        is_platform_admin=True,
        credential_id=cred.id,
        provider="openai",
        capability="chat",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        enabled=True,
        items=[("gpt-system-new", "sys-alias")],
    )
    assert failed == []
    assert len(created) == 1
    model_id = created[0]["gateway_model_id"]

    models = GatewayModelRepository(db_session)
    system_row = await models.get_system(model_id)
    assert system_row is not None
    assert system_row.name == "sys-alias"
    assert system_row.credential_id == cred.id
    tenant_row = await models.get(model_id)
    assert tenant_row is None


@pytest.mark.asyncio
async def test_batch_import_system_duplicate_fails_when_in_system_gateway_models(
    db_session, test_user: User
) -> None:
    port = AsyncMock()
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-dup-{uuid.uuid4().hex[:8]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await GatewayModelRepository(db_session).create_system(
        name="catalog-existing",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await db_session.commit()

    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    svc = CredentialUpstreamCatalogService(db_session, port=port)
    created, failed = await svc.batch_import_team_models(
        tenant_id=team.id,
        is_platform_admin=True,
        credential_id=cred.id,
        provider="openai",
        capability="chat",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        enabled=True,
        items=[("gpt-4o-mini", None)],
    )
    assert created == []
    assert len(failed) == 1
    assert failed[0]["upstream_model_id"] == "gpt-4o-mini"
    assert "已注册" in failed[0]["reason"]


@pytest.mark.asyncio
async def test_batch_import_cross_credential_same_upstream_id_succeeds(
    db_session, test_user: User
) -> None:
    port = AsyncMock()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred_a = await create_tenant_test_credential(
        db_session, team.id, name="import-cred-a", provider="openai"
    )
    cred_b = await create_tenant_test_credential(
        db_session, team.id, name="import-cred-b", provider="openai"
    )
    from domains.gateway.application.management.writes import GatewayManagementWriteService

    writes = GatewayManagementWriteService(db_session)
    await writes.create_gateway_model(
        tenant_id=team.id,
        name="alias-on-a",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred_a.id,
        provider="openai",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        is_platform_admin=False,
        enabled=True,
        reload_router=False,
    )
    await db_session.commit()

    svc = CredentialUpstreamCatalogService(db_session, port=port)
    created, failed = await svc.batch_import_team_models(
        tenant_id=team.id,
        is_platform_admin=False,
        credential_id=cred_b.id,
        provider="openai",
        capability="chat",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        enabled=True,
        items=[("gpt-4o-mini", None)],
    )
    assert failed == []
    assert len(created) == 1
    assert created[0]["upstream_model_id"] == "gpt-4o-mini"
