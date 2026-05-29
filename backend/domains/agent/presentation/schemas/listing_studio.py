"""Listing Studio API 请求/响应 Schema。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunStepBody(BaseModel):
    capability_id: str = Field(..., description="能力 ID")
    user_input: dict[str, Any] = Field(default_factory=dict)
    model_id: str | None = Field(None, description="用户模型 UUID 或系统模型 ID")
    meta_prompt: str | None = None
    prompt_template_id: str | None = None


class OptimizePromptBody(BaseModel):
    capability_id: str = Field(..., description="能力 ID")
    user_input: dict[str, Any] = Field(default_factory=dict)
    meta_prompt: str | None = None
    model_id: str | None = Field(None, description="用户模型 UUID 或系统模型 ID")


class RunPipelineBody(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    steps: list[str] | None = None
    session_id: str | None = None
    model_overrides: dict[str, str] | None = Field(
        default=None,
        description="按 capability_id 指定各步 model_id",
    )


class CreateTemplateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    content: str | None = None
    prompts: list[str] | None = None


class UpdateTemplateBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    content: str | None = None
    prompts: list[str] | None = None


class CreateImageGenTaskBody(BaseModel):
    prompts: list[dict[str, Any]] = Field(default_factory=list)
    job_id: str | None = None
    model_id: str | None = None
    provider: str | None = None
    size: str | None = None
    reference_image_url: str | None = None
    strength: float | None = None


class ListingStudioJobStepResponse(BaseModel):
    id: str
    job_id: str
    sort_order: int
    capability_id: str
    input_snapshot: dict[str, Any] | None = None
    output_snapshot: dict[str, Any] | None = None
    meta_prompt: str | None = None
    generated_prompt: str | None = None
    prompt_used: str | None = None
    prompt_template_id: str | None = None
    status: str
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ListingStudioJobResponse(BaseModel):
    id: str
    user_id: str | None = None
    session_id: str | None = None
    title: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    steps: list[ListingStudioJobStepResponse] = Field(default_factory=list)


class ListingStudioJobListResponse(BaseModel):
    items: list[ListingStudioJobResponse]
    total: int
    skip: int
    limit: int


class ListingStudioCapabilitiesResponse(BaseModel):
    capabilities: list[dict[str, Any]]
    execution_layers: list[list[str]]


class RunPipelineResponse(BaseModel):
    job_id: str
    status: str
    message: str
    poll_url: str


class OptimizePromptResponse(BaseModel):
    capability_id: str
    optimized_prompt: str


class UploadImageResponse(BaseModel):
    url: str
    content_type: str
    size_bytes: int


def job_response(data: dict[str, Any]) -> ListingStudioJobResponse:
    return ListingStudioJobResponse.model_validate(data)


def job_list_response(
    items: list[dict[str, Any]],
    *,
    total: int,
    skip: int,
    limit: int,
) -> ListingStudioJobListResponse:
    return ListingStudioJobListResponse(
        items=[job_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


__all__ = [
    "CreateImageGenTaskBody",
    "CreateTemplateBody",
    "ListingStudioCapabilitiesResponse",
    "ListingStudioJobListResponse",
    "ListingStudioJobResponse",
    "ListingStudioJobStepResponse",
    "OptimizePromptBody",
    "OptimizePromptResponse",
    "RunPipelineBody",
    "RunPipelineResponse",
    "RunStepBody",
    "UpdateTemplateBody",
    "job_list_response",
    "job_response",
]
