"""上游 Provider Profile SSOT API 响应。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderProfileApiBaseResponse(BaseModel):
    openai_compat: str | None = None
    anthropic_native: str | None = None


class ProviderProfileResponse(BaseModel):
    id: str
    provider: str
    label: str
    api_bases: ProviderProfileApiBaseResponse
    models_list_path: str = "/models"
    default_call_shape: str = "openai_compat"
    probe_supported: bool = True


class ProviderProfilesListResponse(BaseModel):
    profiles: list[ProviderProfileResponse] = Field(default_factory=list)


__all__ = [
    "ProviderProfileApiBaseResponse",
    "ProviderProfileResponse",
    "ProviderProfilesListResponse",
]
