"""credential_env_audit 启动诊断单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pydantic import SecretStr
import pytest

from bootstrap.config import Settings
from domains.gateway.application.credential.credential_env_audit import log_config_managed_api_base_drift
from domains.gateway.domain.credential.credential_sync_policy import FORCE_ENV_SYNC_EXTRA_KEY
from domains.gateway.domain.types import CONFIG_MANAGED_BY

CODING_ZHIPU_BASE = "https://open.bigmodel.cn/api/coding/paas/v4"
DEFAULT_ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"


@pytest.mark.asyncio
async def test_audit_no_warning_when_db_empty_and_env_uses_pydantic_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit._BOOTSTRAP_PROVIDERS",
        ("zhipuai",),
    )
    session = MagicMock()
    settings = Settings(
        zhipuai_api_key=SecretStr("sk-test"),
        zhipuai_api_base=DEFAULT_ZHIPU_BASE,
    )
    row = SimpleNamespace(
        api_base=None,
        extra={"managed_by": CONFIG_MANAGED_BY},
    )
    repo = SimpleNamespace(find_config_managed=AsyncMock(return_value=row))
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit.SystemProviderCredentialRepository",
        lambda _session: repo,
    )

    warnings: list[str] = []
    info_logs: list[str] = []
    logger = MagicMock()
    logger.warning.side_effect = lambda msg, *args: warnings.append(msg % args if args else msg)
    logger.info.side_effect = lambda msg, *args: info_logs.append(msg % args if args else msg)
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit.logger",
        logger,
    )

    await log_config_managed_api_base_drift(session, settings)

    assert not warnings


@pytest.mark.asyncio
async def test_audit_warns_when_db_empty_and_env_has_non_default_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit._BOOTSTRAP_PROVIDERS",
        ("zhipuai",),
    )
    session = MagicMock()
    settings = Settings(
        zhipuai_api_key=SecretStr("sk-test"),
        zhipuai_api_base=CODING_ZHIPU_BASE,
    )
    row = SimpleNamespace(
        api_base=None,
        extra={"managed_by": CONFIG_MANAGED_BY},
    )
    repo = SimpleNamespace(find_config_managed=AsyncMock(return_value=row))
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit.SystemProviderCredentialRepository",
        lambda _session: repo,
    )

    warnings: list[str] = []
    logger = MagicMock()
    logger.warning.side_effect = lambda msg, *args: warnings.append(msg % args if args else msg)
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit.logger",
        logger,
    )

    await log_config_managed_api_base_drift(session, settings)

    assert len(warnings) == 1
    assert CODING_ZHIPU_BASE in warnings[0]


@pytest.mark.asyncio
async def test_audit_info_on_drift_when_config_managed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit._BOOTSTRAP_PROVIDERS",
        ("zhipuai",),
    )
    session = MagicMock()
    settings = Settings(
        zhipuai_api_key=SecretStr("sk-test"),
        zhipuai_api_base=CODING_ZHIPU_BASE,
    )
    row = SimpleNamespace(
        api_base=DEFAULT_ZHIPU_BASE,
        extra={"managed_by": CONFIG_MANAGED_BY, FORCE_ENV_SYNC_EXTRA_KEY: False},
    )
    repo = SimpleNamespace(find_config_managed=AsyncMock(return_value=row))
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit.SystemProviderCredentialRepository",
        lambda _session: repo,
    )

    info_logs: list[str] = []
    logger = MagicMock()
    logger.info.side_effect = lambda msg, *args: info_logs.append(msg % args if args else msg)
    monkeypatch.setattr(
        "domains.gateway.application.credential.credential_env_audit.logger",
        logger,
    )

    await log_config_managed_api_base_drift(session, settings)

    assert len(info_logs) == 1
    assert DEFAULT_ZHIPU_BASE in info_logs[0]
    assert CODING_ZHIPU_BASE in info_logs[0]
