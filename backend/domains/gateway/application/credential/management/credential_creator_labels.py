"""凭据「提供者」展示标签（管理 API 列表 / 摘要）。"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from domains.gateway.domain.types import (
    CredentialScope,
    credential_api_scope,
    is_config_managed_system_credential,
)
from domains.identity.application.ports import UserSummaryView, user_display_label

from .credential_read_model import CredentialReadModel


def collect_creator_user_ids(creds: Sequence[CredentialReadModel]) -> list[UUID]:
    """批量解析创建者 user_id（team 凭据 + BYOK scope_id）。"""
    ids: set[UUID] = set()
    for cred in creds:
        if cred.created_by_user_id is not None:
            ids.add(cred.created_by_user_id)
            continue
        api_scope = credential_api_scope(scope=cred.scope, tenant_id=cred.tenant_id)
        if api_scope == CredentialScope.USER.value and cred.scope_id is not None:
            ids.add(cred.scope_id)
    return sorted(ids)


def credential_creator_display_label(
    cred: CredentialReadModel,
    *,
    user_label: str | None,
) -> str | None:
    """将 read model + 用户摘要转为列表「提供者」文案。"""
    api_scope = credential_api_scope(scope=cred.scope, tenant_id=cred.tenant_id)
    config_managed = is_config_managed_system_credential(
        scope=cred.scope,
        tenant_id=cred.tenant_id,
        name=cred.name,
        extra=cred.extra,
    )
    if api_scope == CredentialScope.SYSTEM.value:
        return "平台（配置同步）" if config_managed else "平台"
    if api_scope == CredentialScope.USER.value:
        return user_label or "个人"
    return user_label


def credential_creator_labels_for_read_models(
    creds: Sequence[CredentialReadModel],
    summaries: dict[UUID, UserSummaryView],
) -> dict[UUID, str | None]:
    """按凭据 id 返回提供者展示标签。"""
    labels: dict[UUID, str | None] = {}
    for cred in creds:
        uid = cred.created_by_user_id
        if uid is None:
            api_scope = credential_api_scope(scope=cred.scope, tenant_id=cred.tenant_id)
            if api_scope == CredentialScope.USER.value:
                uid = cred.scope_id
        user_label = user_display_label(summaries.get(uid)) if uid is not None else None
        labels[cred.id] = credential_creator_display_label(cred, user_label=user_label)
    return labels


__all__ = [
    "collect_creator_user_ids",
    "credential_creator_display_label",
    "credential_creator_labels_for_read_models",
]
