"""启动时对比 env bootstrap 与 DB config-managed 凭据 api_base（仅日志）。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import Settings
from domains.gateway.domain.provider_api_base import get_default_api_base
from domains.gateway.domain.provider_env_catalog import (
    ProviderEnvSnapshot,
    provider_env_snapshot_from_settings,
    resolve_provider_credentials,
)
from domains.gateway.domain.types import CONFIG_MANAGED_BY
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from utils.logging import get_logger

logger = get_logger(__name__)

_BOOTSTRAP_PROVIDERS: tuple[str, ...] = (
    "openai",
    "deepseek",
    "dashscope",
    "zhipuai",
    "volcengine",
)


def _raw_env_api_base(snapshot: ProviderEnvSnapshot, provider: str) -> str | None:
    """Settings 快照中的原始 base（未套用 domain 默认）。"""
    attr = f"{provider}_api_base"
    raw = getattr(snapshot, attr, None)
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    return stripped or None


async def log_config_managed_api_base_drift(session: AsyncSession, settings: Settings) -> None:
    """env 与 DB api_base 不一致时打 info/warning；不阻断启动。"""
    snapshot = provider_env_snapshot_from_settings(settings)
    repo = SystemProviderCredentialRepository(session)

    for provider in _BOOTSTRAP_PROVIDERS:
        creds = resolve_provider_credentials(provider, snapshot)
        if creds is None or not creds.api_key:
            continue

        env_base = (creds.api_base or "").strip()
        row = await repo.find_config_managed(provider)
        if row is None:
            if env_base:
                logger.info(
                    "Gateway credential bootstrap: %s has env api_base but no config-managed "
                    "system credential yet (catalog sync will create)",
                    provider,
                )
            continue

        db_base = (row.api_base or "").strip()
        raw_env_base = _raw_env_api_base(snapshot, provider)
        default_base = get_default_api_base(provider)
        if not db_base and raw_env_base and raw_env_base != (default_base or ""):
            logger.warning(
                "Gateway credential %s: DB api_base empty but env has non-default %s; "
                "run catalog sync or set base in management UI",
                provider,
                raw_env_base,
            )
            continue

        if db_base and env_base and db_base != env_base:
            managed_by = (row.extra or {}).get("managed_by")
            if managed_by == CONFIG_MANAGED_BY:
                logger.info(
                    "Gateway credential %s: DB api_base=%s (management/sync authoritative); "
                    "env ZHIPUAI_API_BASE-style value=%s not auto-applied on sync",
                    provider,
                    db_base,
                    env_base,
                )
