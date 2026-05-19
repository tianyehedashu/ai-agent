"""GatewayVirtualKey ORM → VirtualKeyReadModel。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.management.virtual_key_read_model import VirtualKeyReadModel

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey


def virtual_key_from_orm(record: GatewayVirtualKey) -> VirtualKeyReadModel:
    return VirtualKeyReadModel(
        id=record.id,
        team_id=record.team_id,
        name=record.name,
        description=record.description,
        masked_key_display=record.masked_key_display,
        allowed_models=tuple(record.allowed_models or ()),
        allowed_capabilities=tuple(record.allowed_capabilities or ()),
        rpm_limit=record.rpm_limit,
        tpm_limit=record.tpm_limit,
        store_full_messages=record.store_full_messages,
        guardrail_enabled=record.guardrail_enabled,
        is_system=record.is_system,
        is_active=record.is_active,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        usage_count=record.usage_count,
        created_at=record.created_at,
        encrypted_key=record.encrypted_key,
    )


__all__ = ["virtual_key_from_orm"]
