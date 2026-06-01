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


@dataclass(frozen=True, slots=True)
class ProbeTarget:
    model_id: uuid.UUID
    capability: str
    provider: str
    real_model: str
    credential_id: uuid.UUID
    is_system: bool


__all__ = ["EncryptedCredentialSnapshot", "ProbeTarget"]
