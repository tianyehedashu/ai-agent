"""个人团队 gateway_models 辅助：能力映射、命名与选择器形状转换。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from domains.gateway.application.config_catalog_sync import (
    model_types_for_gateway_registration,
    selector_capabilities_from_tags,
)
from domains.gateway.domain.model_types_tags import (
    capability_for_model_type,
    tags_from_model_types,
)
from domains.gateway.domain.types import PERSONAL_MODEL_TYPES

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel

VALID_PERSONAL_MODEL_TYPES = PERSONAL_MODEL_TYPES


def tags_for_model_type(model_type: str) -> dict[str, Any]:
    """创建 personal 行时的初始 tags（SSOT：``model_types_tags``，仅写入 true 标记）。"""
    mtype = model_type.strip().lower()
    if mtype not in PERSONAL_MODEL_TYPES:
        return {}
    capability = capability_for_model_type(mtype)
    merged = tags_from_model_types(
        [mtype],
        existing_tags={},
        capability=capability,
        clear_unselected=False,
    )
    return {key: value for key, value in merged.items() if value is True}


def slugify_display_name(display_name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", display_name.strip().lower()).strip("-")
    return base[:80] if base else "model"


def personal_model_alias(display_name: str, model_type: str, *, suffix: int = 0) -> str:
    slug = slugify_display_name(display_name)
    cap = capability_for_model_type(model_type)
    parts = [slug, model_type if model_type != "text" else "", cap]
    if suffix > 0:
        parts.append(str(suffix))
    return "-".join(p for p in parts if p)[:200]


def gateway_model_to_personal_list_item(
    row: GatewayModel,
    *,
    credential_profile_id: str | None = None,
) -> dict[str, Any]:
    """将 personal team 的 GatewayModel 行转为选择器/管理 API 列表项。"""
    tags = row.tags or {}
    display_name = str(tags.get("display_name") or row.name)
    model_types = model_types_for_gateway_registration(tags, row.capability)
    return {
        "id": str(row.id),
        "user_id": None,
        "display_name": display_name,
        "provider": row.provider,
        "model_id": row.real_model,
        "api_key_masked": None,
        "has_api_key": True,
        "api_base": None,
        "credential_id": str(row.credential_id),
        "model_types": model_types,
        "config": None,
        "is_active": row.enabled,
        "is_system": False,
        "capability": row.capability,
        "name": row.name,
        "selector_capabilities": selector_capabilities_from_tags(
            tags,
            provider=row.provider,
            real_model=row.real_model,
            credential_profile_id=credential_profile_id,
        ),
        "last_test_status": row.last_test_status,
        "last_tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
        "last_test_reason": row.last_test_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def gateway_model_to_selector_user_item(row: GatewayModel) -> dict[str, Any]:
    """供聊天选择器 personal_models 段使用的条目（id 为 gateway_models UUID）。"""
    item = gateway_model_to_personal_list_item(row)
    item["is_system"] = False
    return item


__all__ = [
    "VALID_PERSONAL_MODEL_TYPES",
    "capability_for_model_type",
    "gateway_model_to_personal_list_item",
    "gateway_model_to_selector_user_item",
    "personal_model_alias",
    "slugify_display_name",
    "tags_for_model_type",
]
