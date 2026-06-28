"""虚拟 Key 只读模型（presentation 响应映射）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class VirtualKeyReadModel:
    id: UUID
    tenant_id: UUID
    team_id: UUID
    name: str
    description: str | None
    masked_key_display: str
    allowed_models: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    rpm_limit: int | None
    tpm_limit: int | None
    store_full_messages: bool
    guardrail_enabled: bool
    is_system: bool
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    usage_count: int
    created_at: datetime
    encrypted_key: str
    granted_team_ids: tuple[UUID, ...] = ()


__all__ = ["VirtualKeyReadModel"]
