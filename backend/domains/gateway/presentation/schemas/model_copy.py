"""模型跨团队子集复制 — Pydantic 契约。"""

from __future__ import annotations

from typing import Literal
import uuid

from pydantic import BaseModel, Field, model_validator


class ModelCopyCredentialPlanRequest(BaseModel):
    source_credential_id: uuid.UUID
    mode: Literal["existing", "copy_credential"]
    destination_credential_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_mode_fields(self) -> ModelCopyCredentialPlanRequest:
        if self.mode == "existing" and self.destination_credential_id is None:
            raise ValueError("destination_credential_id is required when mode is existing")
        if self.mode == "copy_credential" and self.destination_credential_id is not None:
            raise ValueError("destination_credential_id must be omitted when mode is copy_credential")
        return self


class CopyModelsToTeamRequest(BaseModel):
    model_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)
    destination_team_id: uuid.UUID
    credential_plans: list[ModelCopyCredentialPlanRequest] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_unique_source_credentials(self) -> CopyModelsToTeamRequest:
        source_ids = [plan.source_credential_id for plan in self.credential_plans]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("credential_plans must have unique source_credential_id values")
        return self


class ModelCopySuccessItem(BaseModel):
    source_model_id: str
    new_model_id: str
    name: str


class ModelCopyFailureItem(BaseModel):
    model_id: str
    reason: str


class CopyModelsToTeamResponse(BaseModel):
    succeeded: list[ModelCopySuccessItem] = Field(default_factory=list)
    failed: list[ModelCopyFailureItem] = Field(default_factory=list)


__all__ = [
    "CopyModelsToTeamRequest",
    "CopyModelsToTeamResponse",
    "ModelCopyCredentialPlanRequest",
    "ModelCopyFailureItem",
    "ModelCopySuccessItem",
]
