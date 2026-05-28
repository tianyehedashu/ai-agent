"""Gateway 配置目录同步单元测试。"""

from __future__ import annotations

import pytest

from bootstrap.config import settings
from domains.gateway.application.config_catalog_sync import (
    MANAGED_CONFIG,
    SYSTEM_CREDENTIAL_NAME,
    _config_managed_credential_extra,
    _ensure_system_credential,
    _merge_config_managed_credential_extra,
    sync_app_config_gateway_catalog,
)
from domains.gateway.domain.credential_sync_policy import FORCE_ENV_SYNC_EXTRA_KEY
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from libs.crypto import derive_encryption_key, encrypt_value


def test_volcengine_managed_extra_seeds_endpoint_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """火山 chat endpoint 写入 system 凭据 extra（非 Agent settings 直读）。"""
    monkeypatch.setattr(settings, "volcengine_chat_endpoint_id", "ep-volc-test")
    monkeypatch.setattr(settings, "volcengine_endpoint_id", None)
    extra = _config_managed_credential_extra("volcengine")
    assert extra.get("endpoint_id") == "ep-volc-test"
    assert extra.get("managed_by") == MANAGED_CONFIG


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
    rows = await repo.list_system(only_enabled=False)
    managed = [r for r in rows if (r.tags or {}).get("managed_by") == MANAGED_CONFIG]
    # 无环境 API Key 时可能 0 行，仅校验结构一致性
    for r in managed:
        assert r.name
        assert r.real_model


@pytest.mark.asyncio
async def test_sync_disables_config_models_when_provider_key_revoked(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """provider API key 撤回后再次同步：之前的 system 模型应被 disable，
    且 system 凭据 ``is_active=False``。"""
    # 第一次：保证 openai key 存在 → catalog 写入 claude/gpt-4o 等系统模型
    monkeypatch.setattr(
        "domains.gateway.application.config_catalog_sync._provider_api_key_and_base",
        lambda p: ("sk-test", None) if p == "openai" else (None, None),
    )
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()

    cred_repo = SystemProviderCredentialRepository(db_session)
    repo = GatewayModelRepository(db_session)
    seeded = await repo.list_system(only_enabled=True)
    openai_rows_before = [r for r in seeded if r.provider == "openai"]
    if not openai_rows_before:
        pytest.skip("openai not present in app.toml catalog")
    openai_creds_before = [c for c in await cred_repo.list_all() if c.provider == "openai"]
    assert openai_creds_before and all(c.is_active for c in openai_creds_before)

    # 第二次：撤回 openai key → 既有 system 模型应被 disable + 凭据失活
    monkeypatch.setattr(
        "domains.gateway.application.config_catalog_sync._provider_api_key_and_base",
        lambda _provider: (None, None),
    )
    stats = await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()

    assert stats["disabled"] >= len(openai_rows_before)
    assert stats["credentials_deactivated"] >= len(openai_creds_before)
    openai_rows_after = [
        r for r in await repo.list_system(only_enabled=False) if r.provider == "openai"
    ]
    assert openai_rows_after and all(not r.enabled for r in openai_rows_after)
    openai_creds_after = [c for c in await cred_repo.list_all() if c.provider == "openai"]
    assert openai_creds_after and all(not c.is_active for c in openai_creds_after)


@pytest.mark.asyncio
async def test_sync_does_not_duplicate_system_credential_after_rename(db_session) -> None:
    """重命名配置托管凭据后再次同步，同一 provider 不应出现第二条 system 凭据。"""
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = SystemProviderCredentialRepository(db_session)
    created = await cred_repo.create(
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

    system_openai = [c for c in await cred_repo.list_all() if c.provider == "openai"]
    assert len(system_openai) == 1
    assert system_openai[0].id == created.id


CODING_ZHIPU_BASE = "https://open.bigmodel.cn/api/coding/paas/v4"
MANAGED_ZHIPU_BASE = "https://admin-managed.example.com/v1"


@pytest.mark.asyncio
async def test_sync_preserves_existing_api_base_over_env(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """管理面已设置的 api_base 不应被 catalog sync 的 env 覆盖。"""
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = SystemProviderCredentialRepository(db_session)

    monkeypatch.setattr(
        "domains.gateway.application.config_catalog_sync._provider_api_key_and_base",
        lambda _p: ("sk-zhipu", CODING_ZHIPU_BASE),
    )
    created_id = await _ensure_system_credential(
        db_session, provider="zhipuai", encryption_key=encryption_key
    )
    assert created_id is not None
    await cred_repo.update(created_id, api_base=MANAGED_ZHIPU_BASE)
    await db_session.flush()

    await _ensure_system_credential(db_session, provider="zhipuai", encryption_key=encryption_key)
    await db_session.flush()

    row = await cred_repo.get(created_id)
    assert row is not None
    assert row.api_base == MANAGED_ZHIPU_BASE


@pytest.mark.asyncio
async def test_sync_backfills_empty_api_base_from_env(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = SystemProviderCredentialRepository(db_session)

    monkeypatch.setattr(
        "domains.gateway.application.config_catalog_sync._provider_api_key_and_base",
        lambda _p: ("sk-zhipu", CODING_ZHIPU_BASE),
    )
    created_id = await _ensure_system_credential(
        db_session, provider="zhipuai", encryption_key=encryption_key
    )
    assert created_id is not None
    await cred_repo.update(created_id, api_base=None)
    await db_session.flush()

    await _ensure_system_credential(db_session, provider="zhipuai", encryption_key=encryption_key)
    await db_session.flush()

    row = await cred_repo.get(created_id)
    assert row is not None
    assert row.api_base == CODING_ZHIPU_BASE
    assert row.api_bases is not None
    assert row.api_bases.get("openai_compat") == CODING_ZHIPU_BASE


def test_merge_config_managed_extra_preserves_force_env_sync() -> None:
    merged = _merge_config_managed_credential_extra(
        "openai",
        {FORCE_ENV_SYNC_EXTRA_KEY: True, "custom_flag": "keep"},
    )
    assert merged[FORCE_ENV_SYNC_EXTRA_KEY] is True
    assert merged["custom_flag"] == "keep"
    assert merged["managed_by"] == MANAGED_CONFIG


@pytest.mark.asyncio
async def test_sync_force_env_sync_overwrites_managed_base(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """extra.force_env_sync=true 时 catalog sync 用 env 覆盖已有 api_base。"""
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = SystemProviderCredentialRepository(db_session)

    monkeypatch.setattr(
        "domains.gateway.application.config_catalog_sync._provider_api_key_and_base",
        lambda _p: ("sk-zhipu", CODING_ZHIPU_BASE),
    )
    created_id = await _ensure_system_credential(
        db_session, provider="zhipuai", encryption_key=encryption_key
    )
    assert created_id is not None
    await cred_repo.update(
        created_id,
        api_base=MANAGED_ZHIPU_BASE,
        extra={"managed_by": MANAGED_CONFIG, FORCE_ENV_SYNC_EXTRA_KEY: True},
    )
    await db_session.flush()

    await _ensure_system_credential(db_session, provider="zhipuai", encryption_key=encryption_key)
    await db_session.flush()

    row = await cred_repo.get(created_id)
    assert row is not None
    assert row.api_base == CODING_ZHIPU_BASE
    assert row.api_bases is not None
    assert row.api_bases.get("openai_compat") == CODING_ZHIPU_BASE
    assert row.extra is not None
    assert row.extra.get(FORCE_ENV_SYNC_EXTRA_KEY) is True
