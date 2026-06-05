"""个人凭据 + 模型批量导入到团队 — Pydantic 契约。"""

from __future__ import annotations

from typing import Any
import uuid

from pydantic import BaseModel, Field

from domains.gateway.presentation.schemas.common import CredentialResponse
from domains.gateway.presentation.schemas.credential_upstream_catalog import (
    BatchImportFailureItem,
)


class ImportCredentialsWithModelsRequest(BaseModel):
    credential_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class ImportedModelSummary(BaseModel):
    source_model_id: str | None = None
    name: str
    real_model: str


class ModelImportFailureItem(BaseModel):
    model_name: str
    reason: str


class ImportedCredentialItemResponse(BaseModel):
    source_credential_id: uuid.UUID
    new_credential: CredentialResponse
    models_created: list[ImportedModelSummary] = Field(default_factory=list)
    models_failed: list[ModelImportFailureItem] = Field(default_factory=list)


class ImportCredentialsWithModelsResponse(BaseModel):
    succeeded: list[ImportedCredentialItemResponse] = Field(default_factory=list)
    failed: list[BatchImportFailureItem] = Field(default_factory=list)


__all__ = [
    "ImportCredentialsWithModelsRequest",
    "ImportCredentialsWithModelsResponse",
    "ImportedCredentialItemResponse",
    "ImportedModelSummary",
    "ModelImportFailureItem",
]
