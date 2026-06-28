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
    profile_id: str | None = None
    profile_label: str | None = None
    api_bases: dict[str, str] | None = None
    effective_api_base_openai: str | None = None
    effective_api_base_anthropic: str | None = None
    visibility: str | None = None
    api_key_masked: str | None = None
    created_by_user_id: UUID | None = None


__all__ = ["CredentialReadModel"]
