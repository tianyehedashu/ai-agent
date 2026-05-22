"""凭据上游探测与批量导入 — 管理 API Pydantic 契约（与前端 gateway.ts 对齐）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, model_validator


class UpstreamModelItemResponse(BaseModel):
    id: str
    owned_by: str | None = None
    already_registered: bool = False
    registered_names: list[str] = Field(default_factory=list)
    inferred_model_types: list[str] = Field(default_factory=list)


class CredentialProbeResponse(BaseModel):
    credential_id: uuid.UUID
    probe_at: datetime
    support: Literal["full", "partial", "unsupported", "error"]
    upstream: Literal["openai_compatible", "none"]
    items: list[UpstreamModelItemResponse] = Field(default_factory=list)
    message: str | None = None
    http_status: int | None = None


class PersonalModelBatchImportItemBody(BaseModel):
    upstream_model_id: str = Field(..., min_length=1, max_length=200)
    model_types: list[str] = Field(..., min_length=1, max_length=4)


class PersonalModelBatchImportRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    items: list[PersonalModelBatchImportItemBody] | None = Field(
        None,
        min_length=1,
        max_length=50,
        description="按条指定 model_types（优先于 upstream_model_ids + model_types）",
    )
    upstream_model_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="deprecated：与 model_types 一起使用",
    )
    model_types: list[str] = Field(default_factory=lambda: ["text"])
    display_name_prefix: str | None = Field(None, max_length=100)
    enabled: bool = True
    tags: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _require_import_source(self) -> PersonalModelBatchImportRequest:
        has_items = self.items is not None and len(self.items) > 0
        has_legacy = len(self.upstream_model_ids) > 0
        if not has_items and not has_legacy:
            raise ValueError("请提供 items 或 upstream_model_ids")
        return self


class PersonalModelBatchImportCreatedItem(BaseModel):
    upstream_model_id: str
    gateway_model_ids: list[uuid.UUID]


class BatchImportFailureItem(BaseModel):
    upstream_model_id: str
    reason: str


class PersonalModelBatchImportResponse(BaseModel):
    credential_id: uuid.UUID
    created: list[PersonalModelBatchImportCreatedItem]
    failed: list[BatchImportFailureItem]


class TeamGatewayModelBatchImportItem(BaseModel):
    upstream_model_id: str = Field(..., min_length=1, max_length=200)
    name: str | None = Field(None, max_length=200)


class TeamGatewayModelBatchImportRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    capability: str = Field(default="chat", min_length=1, max_length=40)
    weight: int = Field(default=1, ge=1)
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    tags: dict[str, Any] | None = None
    enabled: bool = True
    items: list[TeamGatewayModelBatchImportItem] = Field(..., min_length=1, max_length=50)


class TeamGatewayModelBatchImportCreatedItem(BaseModel):
    upstream_model_id: str
    gateway_model_id: uuid.UUID


class TeamGatewayModelBatchImportResponse(BaseModel):
    credential_id: uuid.UUID
    created: list[TeamGatewayModelBatchImportCreatedItem]
    failed: list[BatchImportFailureItem]


__all__ = [
    "BatchImportFailureItem",
    "CredentialProbeResponse",
    "PersonalModelBatchImportCreatedItem",
    "PersonalModelBatchImportItemBody",
    "PersonalModelBatchImportRequest",
    "PersonalModelBatchImportResponse",
    "TeamGatewayModelBatchImportCreatedItem",
    "TeamGatewayModelBatchImportItem",
    "TeamGatewayModelBatchImportRequest",
    "TeamGatewayModelBatchImportResponse",
    "UpstreamModelItemResponse",
]
