"""个人资源 grant API schemas。"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ResourceGrantCreateRequest(BaseModel):
    subject_kind: str = Field(..., pattern="^(credential|model)$")
    subject_id: uuid.UUID
    target_team_ids: list[uuid.UUID] = Field(..., min_length=1)
    note: str | None = None


class ResourceGrantUpdateRequest(BaseModel):
    enabled: bool | None = None
    note: str | None = None


class ResourceGrantResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    subject_kind: str
    subject_id: uuid.UUID
    target_team_id: uuid.UUID
    enabled: bool
    note: str | None
    granted_by: uuid.UUID

    model_config = {"from_attributes": True}


class GrantedModelResponse(BaseModel):
    model_id: uuid.UUID
    name: str
    real_model: str
    provider: str
    capability: str
    credential_id: uuid.UUID
    owner_user_id: uuid.UUID
    personal_team_id: uuid.UUID


__all__ = [
    "GrantedModelResponse",
    "ResourceGrantCreateRequest",
    "ResourceGrantResponse",
    "ResourceGrantUpdateRequest",
]
