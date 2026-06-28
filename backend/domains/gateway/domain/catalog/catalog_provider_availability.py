"""配置目录同步：provider 不可用时，决定哪些 system 行应当退场。

纯函数与值对象，不依赖 ORM / Session / Settings；供
``application.config_catalog_sync`` 在拿到"快照"后调用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from domains.gateway.domain.types import CONFIG_MANAGED_BY, GATEWAY_MODEL_MANAGED_BY_TAG

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    import uuid


class _SystemModelSnapshot(Protocol):
    id: uuid.UUID
    name: str
    provider: str
    credential_id: uuid.UUID
    enabled: bool
    tags: dict[str, object] | None


class _SystemCredentialSnapshot(Protocol):
    id: uuid.UUID
    provider: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class CatalogProviderRetirementPlan:
    """provider key 撤掉时，需要 disable 的 system 模型 / 失活的 system 凭据。"""

    model_ids_to_disable: tuple[uuid.UUID, ...]
    credential_ids_to_deactivate: tuple[uuid.UUID, ...]
    affected_model_names: tuple[str, ...]


def _is_config_managed(row: _SystemModelSnapshot) -> bool:
    tags = row.tags or {}
    return tags.get(GATEWAY_MODEL_MANAGED_BY_TAG) == CONFIG_MANAGED_BY


def build_catalog_provider_retirement_plan(
    *,
    providers_without_key: Iterable[str],
    system_models: Sequence[_SystemModelSnapshot],
    system_credentials: Sequence[_SystemCredentialSnapshot],
) -> CatalogProviderRetirementPlan:
    """计算"凭据已撤回"的 system 行退场计划。

    - 仅处理 ``managed_by=config`` 的 system 模型（人工创建/团队级行不动）。
    - 仅停用当前仍 ``enabled=True`` 的行；幂等。
    - 同 provider 下所有 system 凭据 ``is_active=True → False``（幂等，不删行，
      便于再次配置 key 时恢复）。
    """
    skip = {p.strip().lower() for p in providers_without_key if p}
    if not skip:
        return CatalogProviderRetirementPlan((), (), ())

    model_ids: list[uuid.UUID] = []
    names: list[str] = []
    for row in system_models:
        if row.provider.strip().lower() not in skip:
            continue
        if not _is_config_managed(row):
            continue
        if not row.enabled:
            continue
        model_ids.append(row.id)
        names.append(row.name)

    cred_ids: list[uuid.UUID] = []
    for cred in system_credentials:
        if cred.provider.strip().lower() not in skip:
            continue
        if not cred.is_active:
            continue
        cred_ids.append(cred.id)

    return CatalogProviderRetirementPlan(
        model_ids_to_disable=tuple(model_ids),
        credential_ids_to_deactivate=tuple(cred_ids),
        affected_model_names=tuple(names),
    )


__all__ = [
    "CatalogProviderRetirementPlan",
    "build_catalog_provider_retirement_plan",
]
