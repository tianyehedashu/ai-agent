"""凭据只读模型（presentation 掩码/解密用，不含 ORM）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class CredentialReadModel:
    id: UUID
    tenant_id: UUID | None
    scope: str | None
    scope_id: UUID | None
    provider: str
    name: str
    api_base: str | None
    extra: dict[str, Any] | None
    is_active: bool
    created_at: datetime
    api_key_encrypted: str


__all__ = ["CredentialReadModel"]
