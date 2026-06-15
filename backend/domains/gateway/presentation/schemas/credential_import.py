"""个人凭据 + 模型批量导入到团队 — Pydantic 契约。"""

from __future__ import annotations

from typing import Literal
import uuid

from pydantic import BaseModel, Field, model_validator

from domains.gateway.presentation.schemas.common import CredentialResponse


class CredentialCopyEndpoint(BaseModel):
    kind: Literal["personal", "team"]
    team_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def team_id_required_for_team_kind(self) -> CredentialCopyEndpoint:
        if self.kind == "team" and self.team_id is None:
            raise ValueError("team_id is required when kind is team")
        return self


class CopyCredentialsWithModelsRequest(BaseModel):
    credential_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)
    source: CredentialCopyEndpoint
    destination: CredentialCopyEndpoint


class ImportCredentialsWithModelsRequest(BaseModel):
    credential_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class ImportedModelSummary(BaseModel):
    source_model_id: str | None = None
    name: str
    real_model: str


class ModelImportFailureItem(BaseModel):
    model_name: str
    reason: str


class CredentialCopyFailureItem(BaseModel):
    credential_id: str
    reason: str


class ImportedCredentialItemResponse(BaseModel):
    source_credential_id: uuid.UUID
    new_credential: CredentialResponse
    models_created: list[ImportedModelSummary] = Field(default_factory=list)
    models_failed: list[ModelImportFailureItem] = Field(default_factory=list)


class ImportCredentialsWithModelsResponse(BaseModel):
    succeeded: list[ImportedCredentialItemResponse] = Field(default_factory=list)
    failed: list[CredentialCopyFailureItem] = Field(default_factory=list)


__all__ = [
    "CopyCredentialsWithModelsRequest",
    "CredentialCopyEndpoint",
    "CredentialCopyFailureItem",
    "ImportCredentialsWithModelsRequest",
    "ImportCredentialsWithModelsResponse",
    "ImportedCredentialItemResponse",
    "ImportedModelSummary",
    "ModelImportFailureItem",
]
