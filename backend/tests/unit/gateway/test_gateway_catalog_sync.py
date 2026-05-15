"""Gateway 配置目录同步单元测试。"""

from __future__ import annotations

import pytest

from bootstrap.config import settings
from domains.gateway.application.config_catalog_sync import (
    MANAGED_CONFIG,
    SYSTEM_CREDENTIAL_NAME,
    sync_app_config_gateway_catalog,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from libs.crypto import derive_encryption_key, encrypt_value


@pytest.mark.asyncio
async def test_sync_app_config_gateway_catalog_idempotent(db_session) -> None:
    """同步可重复执行且不抛错。"""
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()


@pytest.mark.asyncio
async def test_sync_marks_config_managed_tags(db_session) -> None:
    """成功写入的 global 行应带 managed_by=config（在至少同步到一行时）。"""
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    repo = GatewayModelRepository(db_session)
    rows = await repo.list_for_team(None, only_enabled=False)
    managed = [r for r in rows if (r.tags or {}).get("managed_by") == MANAGED_CONFIG]
    # 无环境 API Key 时可能 0 行，仅校验结构一致性
    for r in managed:
        assert r.team_id is None
        assert r.name
        assert r.real_model


@pytest.mark.asyncio
async def test_sync_does_not_duplicate_system_credential_after_rename(db_session) -> None:
    """重命名配置托管凭据后再次同步，同一 provider 不应出现第二条 system 凭据。"""
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    created = await cred_repo.create(
        scope="system",
        scope_id=None,
        provider="openai",
        name=SYSTEM_CREDENTIAL_NAME,
        api_key_encrypted=encrypt_value("sk-sync-test", encryption_key),
        api_base=None,
        extra={"managed_by": MANAGED_CONFIG},
    )
    await cred_repo.update(created.id, name="renamed-openai-config")
    await db_session.flush()

    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()

    system_openai = [
        c
        for c in await cred_repo.list_system()
        if c.provider == "openai"
    ]
    assert len(system_openai) == 1
    assert system_openai[0].id == created.id
