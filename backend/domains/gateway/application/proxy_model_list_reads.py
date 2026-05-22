"""代理端 GET /v1/models 列表组装（OpenAI 形状 + gateway 扩展元数据）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.config_catalog_sync import (
    model_types_for_gateway_registration,
    selector_capabilities_from_tags,
)
from domains.gateway.application.entitlement_model_status import (
    compute_model_callable,
    connectivity_status_from_last_test,
    entitlement_status_by_model_names,
)
from domains.gateway.domain.types import EntitlementListStatus
from domains.gateway.infrastructure.models.gateway_model import GatewayModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _iso_or_none(when: datetime | None) -> str | None:
    if when is None:
        return None
    return when.isoformat()


def build_openai_model_list_item(
    row: GatewayModel,
    *,
    entitlement_status: EntitlementListStatus,
) -> dict[str, object]:
    """单条 OpenAI Model 对象 + ``model_types`` + ``gateway`` 命名空间。"""
    tags = row.tags or {}
    connectivity = connectivity_status_from_last_test(row.last_test_status)
    return {
        "id": row.name,
        "object": "model",
        "created": int(row.created_at.timestamp()),
        "owned_by": row.provider,
        "capability": row.capability,
        "model_types": model_types_for_gateway_registration(tags, row.capability),
        "gateway": {
            "display_name": str(tags.get("display_name") or row.name),
            "real_model": row.real_model,
            "connectivity_status": connectivity,
            "connectivity_tested_at": _iso_or_none(row.last_tested_at),
            "connectivity_reason": row.last_test_reason,
            "entitlement_status": entitlement_status,
            "callable": compute_model_callable(
                connectivity_status=connectivity,
                entitlement_status=entitlement_status,
            ),
            "selector_capabilities": selector_capabilities_from_tags(
                tags, provider=row.provider, real_model=row.real_model
            ),
        },
    }


async def build_proxy_models_list(
    session: AsyncSession,
    models: list[GatewayModel],
    *,
    entitlement_scope: str | None,
    entitlement_scope_id: uuid.UUID | None,
) -> list[dict[str, object]]:
    """批量注入 entitlement 状态并组装代理模型列表。"""
    if not models:
        return []
    names = [m.name for m in models]
    entitlement_by_name = await entitlement_status_by_model_names(
        session,
        scope=entitlement_scope,
        scope_id=entitlement_scope_id,
        model_names=names,
    )
    return [
        build_openai_model_list_item(
            row,
            entitlement_status=entitlement_by_name.get(row.name, "none"),
        )
        for row in models
    ]


__all__ = [
    "build_openai_model_list_item",
    "build_proxy_models_list",
]
