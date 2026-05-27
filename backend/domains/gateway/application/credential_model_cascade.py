"""凭据启用/停用时，同步关联 ``GatewayModel`` / ``SystemGatewayModel`` 的 ``enabled``。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.model_reference_prune import prune_gateway_model_name_references
from domains.gateway.domain.policies.credential_model_cascade import (
    apply_credential_cascade_disable_tags,
    clear_credential_cascade_disable_tags,
    was_credential_cascade_disabled,
)
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository

logger = get_logger(__name__)


async def sync_gateway_models_for_credential_is_active(
    session: AsyncSession,
    models_repo: GatewayModelRepository,
    credential_id: uuid.UUID,
    *,
    is_active: bool,
) -> int:
    """凭据 ``is_active`` 变更时级联模型状态。

    - 停用：将当前 ``enabled=True`` 的关联模型设为 ``enabled=False``，并打标
      ``disabled_by_credential``（便于再次启用时恢复）。
    - 启用：仅恢复带该标记的模型；用户此前手动停用的模型不受影响。
    """
    tenant_models = await models_repo.list_by_credential_id(credential_id)
    system_models = await models_repo.list_system(
        credential_id=credential_id,
        only_enabled=False,
    )
    changed = 0
    disabled_names: list[str] = []

    if is_active:
        for model in tenant_models:
            if not was_credential_cascade_disabled(model.tags):
                continue
            restored_tags = clear_credential_cascade_disable_tags(model.tags) or {}
            await models_repo.update(
                model.id,
                enabled=True,
                tags=restored_tags,
            )
            changed += 1
        for model in system_models:
            if not was_credential_cascade_disabled(model.tags):
                continue
            restored_tags = clear_credential_cascade_disable_tags(model.tags) or {}
            await models_repo.update_system(
                model.id,
                enabled=True,
                tags=restored_tags,
            )
            changed += 1
    else:
        for model in tenant_models:
            if not model.enabled:
                continue
            disabled_names.append(model.name)
            await models_repo.update(
                model.id,
                enabled=False,
                tags=apply_credential_cascade_disable_tags(model.tags),
            )
            changed += 1
        for model in system_models:
            if not model.enabled:
                continue
            disabled_names.append(model.name)
            await models_repo.update_system(
                model.id,
                enabled=False,
                tags=apply_credential_cascade_disable_tags(model.tags),
            )
            changed += 1
        if disabled_names:
            await prune_gateway_model_name_references(session, frozenset(disabled_names))

    if changed:
        logger.info(
            "Credential %s is_active=%s: cascaded %d gateway model(s)",
            credential_id,
            is_active,
            changed,
        )
    return changed


__all__ = ["sync_gateway_models_for_credential_is_active"]
