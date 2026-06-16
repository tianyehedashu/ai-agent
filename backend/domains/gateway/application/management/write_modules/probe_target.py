"""模型探活目标解析（值对象）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import uuid


class EncryptedCredentialSnapshot(Protocol):
    id: uuid.UUID
    name: str
    api_key_encrypted: str
    api_base: str | None
    extra: dict[str, Any] | None
    profile_id: str | None


@dataclass(frozen=True, slots=True)
class ProbeTarget:
    model_id: uuid.UUID
    capability: str
    provider: str
    real_model: str
    credential_id: uuid.UUID
    is_system: bool


@dataclass(frozen=True, slots=True)
class ProbeCredentialSnapshot:
    """探活上游调用用的凭据快照（须在 session rollback 前从 ORM 构建）。"""

    id: uuid.UUID
    name: str
    profile_id: str | None
    api_base: str | None
    extra: dict[str, Any] | None
    api_key: str

    @classmethod
    def from_encrypted(
        cls,
        credential: EncryptedCredentialSnapshot,
        *,
        api_key: str,
    ) -> ProbeCredentialSnapshot:
        extra = credential.extra if isinstance(credential.extra, dict) else None
        profile_id = credential.profile_id
        return cls(
            id=credential.id,
            name=credential.name,
            profile_id=profile_id.strip() if isinstance(profile_id, str) and profile_id.strip() else None,
            api_base=credential.api_base,
            extra=extra,
            api_key=api_key,
        )


__all__ = [
    "EncryptedCredentialSnapshot",
    "ProbeCredentialSnapshot",
    "ProbeTarget",
]
