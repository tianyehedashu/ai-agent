"""config-managed 凭据 bootstrap 时 api_base 写入策略（纯函数）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.provider.provider_api_base import get_default_api_base

FORCE_ENV_SYNC_EXTRA_KEY = "force_env_sync"


def credential_force_env_sync(extra: dict[str, Any] | None) -> bool:
    """凭据 extra 显式要求 catalog sync 用 env 覆盖已有 api_base。"""
    if not extra:
        return False
    return bool(extra.get(FORCE_ENV_SYNC_EXTRA_KEY))


def resolve_bootstrap_api_base(
    *,
    provider: str,
    env_base: str | None,
    existing_base: str | None,
    is_new_credential: bool,
    force_env_sync: bool = False,
) -> str | None:
    """决定 catalog sync 应写入 DB 的 api_base。

    - 新建：``env_base`` 非空优先，否则 ``get_default_api_base``。
    - 已存在且 base 非空：默认保留管理面配置；``force_env_sync`` 时允许 env 覆盖。
    - 已存在且 base 为空：回填 env 或 default。
    """
    candidate = (env_base or "").strip() or get_default_api_base(provider)

    if is_new_credential:
        return candidate

    existing = (existing_base or "").strip()
    if existing and not force_env_sync:
        return existing_base

    return candidate


__all__ = [
    "FORCE_ENV_SYNC_EXTRA_KEY",
    "credential_force_env_sync",
    "resolve_bootstrap_api_base",
]
