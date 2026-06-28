"""模型跨团队子集复制 — 应用层结果类型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import uuid

ModelCopyCredentialMode = Literal["existing", "copy_credential"]


@dataclass(frozen=True)
class ModelCopyCredentialPlan:
    source_credential_id: uuid.UUID
    mode: ModelCopyCredentialMode
    destination_credential_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ModelCopyFailure:
    model_id: str
    reason: str


@dataclass(frozen=True)
class ModelCopySuccess:
    source_model_id: str
    new_model_id: str
    name: str


@dataclass(frozen=True)
class CopyModelsToTeamResult:
    succeeded: list[ModelCopySuccess]
    failed: list[ModelCopyFailure]


__all__ = [
    "CopyModelsToTeamResult",
    "ModelCopyCredentialMode",
    "ModelCopyCredentialPlan",
    "ModelCopyFailure",
    "ModelCopySuccess",
]
