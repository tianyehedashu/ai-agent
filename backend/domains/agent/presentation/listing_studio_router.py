"""
Listing Studio API - Listing 工作流接口
"""

import asyncio
import mimetypes
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from domains.agent.application.chat_model_resolution_use_case import ChatModelResolutionUseCase
from domains.agent.application.listing_studio_image_service import ListingStudioImageService
from domains.agent.application.listing_studio_pipeline import run_pipeline_async
from domains.agent.domain.listing_studio.upload_policy import validate_image_upload
from domains.agent.application.listing_studio_prompt_service import (
    ListingStudioPromptTemplateUseCase,
    get_capabilities_config,
    get_default_prompt,
    list_meta_prompt_params,
)
from domains.agent.application.listing_studio_use_case import ListingStudioUseCase
from domains.agent.application.product_image_gen_task_use_case import (
    ProductImageGenTaskUseCase,
)
from domains.agent.presentation.schemas.listing_studio import (
    CreateImageGenTaskBody,
    CreateTemplateBody,
    ListingStudioCapabilitiesResponse,
    ListingStudioJobListResponse,
    ListingStudioJobResponse,
    OptimizePromptBody,
    OptimizePromptResponse,
    RunPipelineBody,
    RunPipelineResponse,
    RunStepBody,
    UpdateTemplateBody,
    UploadImageResponse,
    job_list_response,
    job_response,
)
from domains.identity.presentation.deps import AuthUser
from domains.session.domain.entities.session import SessionOwner
from libs.api.deps import (
    get_chat_model_resolution_service,
    get_listing_studio_image_service,
    get_listing_studio_prompt_service,
    get_listing_studio_service,
    get_product_image_gen_task_service,
)
from libs.api.params import parse_optional_uuid
from libs.api.paths import api_v1_path
from libs.background_tasks import register_app_background_task
from libs.exceptions import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# Job 相关
# =============================================================================


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    current_user: AuthUser,
    service: ListingStudioUseCase = Depends(get_listing_studio_service),
    title: str | None = Query(None),
    session_id: str | None = Query(None),
) -> ListingStudioJobResponse:
    """创建 Listing 创作任务"""
    session_uuid = parse_optional_uuid(session_id, "session_id")
    data = await service.create_job(
        principal_id=current_user.id,
        session_id=session_uuid,
        title=title,
    )
    return job_response(data)


@router.get("/jobs")
async def list_jobs(
    current_user: AuthUser,
    service: ListingStudioUseCase = Depends(get_listing_studio_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    session_id: str | None = None,
) -> ListingStudioJobListResponse:
    """Listing 创作任务列表"""
    session_uuid = parse_optional_uuid(session_id, "session_id")
    items, total = await service.list_jobs(
        skip=skip,
        limit=limit,
        status=status_filter,
        session_id=session_uuid,
    )
    return job_list_response(items, total=total, skip=skip, limit=limit)


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    current_user: AuthUser,
    service: ListingStudioUseCase = Depends(get_listing_studio_service),
) -> ListingStudioJobResponse:
    """任务详情（含 steps，用于后台查看）"""
    data = await service.get_job(job_id)
    return job_response(data)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    current_user: AuthUser,
    service: ListingStudioUseCase = Depends(get_listing_studio_service),
) -> None:
    """删除任务"""
    await service.delete_job(job_id)


# =============================================================================
# 执行某一步
# =============================================================================


@router.post("/jobs/{job_id}/steps")
async def run_step(
    job_id: uuid.UUID,
    body: RunStepBody,
    current_user: AuthUser,
    service: ListingStudioUseCase = Depends(get_listing_studio_service),
) -> ListingStudioJobResponse:
    """执行工作流中的某一步：渲染提示词后直接执行"""
    template_uuid = None
    if body.prompt_template_id:
        try:
            template_uuid = uuid.UUID(body.prompt_template_id)
        except ValueError:
            raise ValidationError("Invalid prompt_template_id") from None
    data = await service.run_step(
        job_id=job_id,
        capability_id=body.capability_id,
        user_input=body.user_input,
        meta_prompt=body.meta_prompt,
        prompt_template_id=template_uuid,
        model_id=body.model_id,
    )
    return job_response(data)


@router.post("/jobs/{job_id}/optimize-prompt")
async def optimize_prompt(
    job_id: uuid.UUID,
    body: OptimizePromptBody,
    current_user: AuthUser,
    service: ListingStudioUseCase = Depends(get_listing_studio_service),
) -> OptimizePromptResponse:
    """可选：AI 优化提示词，返回优化后的文本供用户确认"""
    optimized = await service.optimize_prompt(
        job_id=job_id,
        capability_id=body.capability_id,
        user_input=body.user_input,
        meta_prompt=body.meta_prompt,
        model_id=body.model_id,
    )
    return OptimizePromptResponse(
        capability_id=body.capability_id,
        optimized_prompt=optimized,
    )


# =============================================================================
# 能力与默认提示词
# =============================================================================


@router.get("/capabilities")
async def get_capabilities() -> ListingStudioCapabilitiesResponse:
    """原子能力列表与 execution_layers（无需认证）"""
    config = get_capabilities_config()
    return ListingStudioCapabilitiesResponse.model_validate(config)


@router.get("/capabilities/{capability_id}/default-prompt")
async def get_capability_default_prompt(capability_id: str) -> dict[str, Any]:
    """系统默认提示词（用于恢复模板）"""
    content = get_default_prompt(capability_id)
    return {"capability_id": capability_id, "content": content}


@router.get("/capabilities/{capability_id}/params")
async def get_capability_params(capability_id: str) -> dict[str, Any]:
    """元提示词可用占位符参数，用于 UI 插入 {{param}}"""
    params = list_meta_prompt_params(capability_id)
    return {"capability_id": capability_id, "params": params}


# =============================================================================
# 用户模板 CRUD
# =============================================================================


@router.get("/capabilities/{capability_id}/templates")
async def list_templates(
    capability_id: str,
    current_user: AuthUser,
    prompt_service: ListingStudioPromptTemplateUseCase = Depends(get_listing_studio_prompt_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """某能力下的用户模板列表"""
    items, total = await prompt_service.list_templates(
        capability_id=capability_id,
        skip=skip,
        limit=limit,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/capabilities/{capability_id}/templates", status_code=status.HTTP_201_CREATED)
async def create_template(
    capability_id: str,
    body: CreateTemplateBody,
    current_user: AuthUser,
    prompt_service: ListingStudioPromptTemplateUseCase = Depends(get_listing_studio_prompt_service),
) -> dict[str, Any]:
    """保存为用户模板"""
    owner = SessionOwner.from_principal_id(current_user.id)
    return await prompt_service.create_template(
        capability_id=capability_id,
        name=body.name,
        content=body.content,
        prompts=body.prompts,
        user_id=owner.user_id,
    )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: uuid.UUID,
    current_user: AuthUser,
    prompt_service: ListingStudioPromptTemplateUseCase = Depends(get_listing_studio_prompt_service),
) -> dict[str, Any]:
    """获取单条模板"""
    return await prompt_service.get_template(template_id)


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: uuid.UUID,
    body: UpdateTemplateBody,
    current_user: AuthUser,
    prompt_service: ListingStudioPromptTemplateUseCase = Depends(get_listing_studio_prompt_service),
) -> dict[str, Any]:
    """更新用户模板"""
    return await prompt_service.update_template(
        template_id,
        name=body.name,
        content=body.content,
        prompts=body.prompts,
    )


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    current_user: AuthUser,
    prompt_service: ListingStudioPromptTemplateUseCase = Depends(get_listing_studio_prompt_service),
) -> None:
    """删除用户模板"""
    await prompt_service.delete_template(template_id)


# =============================================================================
# 一键异步执行
# =============================================================================


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_pipeline(
    request: Request,
    current_user: AuthUser,
    service: ListingStudioUseCase = Depends(get_listing_studio_service),
    body: RunPipelineBody | None = None,
) -> RunPipelineResponse:
    """一键异步执行：创建 Job，后台按依赖分层执行，立即返回 job_id。"""
    if body is None:
        body = RunPipelineBody(model_overrides=None)
    owner = SessionOwner.from_principal_id(current_user.id)
    session_uuid = parse_optional_uuid(body.session_id, "session_id")

    job = await service.create_job(
        principal_id=current_user.id,
        session_id=session_uuid,
        title="一键执行",
        status="running",
    )
    job_id = job["id"]

    pipeline_bg_task = asyncio.create_task(
        run_pipeline_async(
            job_id=uuid.UUID(job_id),
            user_id=owner.user_id,
            inputs=body.inputs or {},
            steps=body.steps,
            model_overrides=body.model_overrides,
        )
    )
    pipeline_bg_task.set_name(f"listing-studio-pipeline:{job_id}")
    register_app_background_task(request.app, pipeline_bg_task)

    return RunPipelineResponse(
        job_id=job_id,
        status="running",
        message="任务已提交，请使用 job_id 在后台查看进度与结果。",
        poll_url=api_v1_path("listing-studio", "jobs", job_id),
    )


# =============================================================================
# 图片上传
# =============================================================================


@router.post("/upload", response_model=UploadImageResponse)
async def upload_image(
    current_user: AuthUser,
    file: UploadFile = File(...),
    image_service: ListingStudioImageService = Depends(get_listing_studio_image_service),
) -> UploadImageResponse:
    """上传图片，返回 URL 供输入区与历史预览使用。"""
    # 如果框架已解析出文件大小，先进行预校验，避免超大文件全部载入内存
    if file.size is not None:
        max_bytes = await image_service.get_upload_max_bytes()
        validate_image_upload(file.content_type, file.size, max_bytes)

    content = await file.read()
    url, content_type, size_bytes = await image_service.upload_image(content, file.content_type)
    return UploadImageResponse(url=url, content_type=content_type, size_bytes=size_bytes)


# =============================================================================
# 8 图生成任务（创建后异步调用 ImageGenerator 生成图片）
# =============================================================================


@router.post("/image-gen", status_code=status.HTTP_201_CREATED)
async def create_image_gen_task(
    current_user: AuthUser,
    image_gen_service: ProductImageGenTaskUseCase = Depends(get_product_image_gen_task_service),
    model_resolution_service: ChatModelResolutionUseCase = Depends(
        get_chat_model_resolution_service
    ),
    body: CreateImageGenTaskBody | None = None,
) -> dict[str, Any]:
    """创建 8 图生成任务。

    model_id 可以是系统模型 (如 "volcengine/seedream") 或用户模型 UUID，
    通过 ChatModelResolutionUseCase 解析为 provider + credentials。
    """
    if body is None:
        body = CreateImageGenTaskBody()

    resolved = await model_resolution_service.resolve_image_gen_model_for_chat(
        body.model_id,
        allowed_image_gen_system_ids=await model_resolution_service.visible_image_gen_system_model_ids(),
    )

    owner = SessionOwner.from_principal_id(current_user.id)
    job_uuid = parse_optional_uuid(body.job_id, "job_id")

    provider = body.provider or resolved.provider
    global_defaults: dict[str, Any] = {"provider": provider}
    if body.size:
        global_defaults["size"] = body.size
    if body.reference_image_url:
        global_defaults["reference_image_url"] = body.reference_image_url
    if body.strength is not None:
        global_defaults["strength"] = body.strength

    prompts = [{**global_defaults, **item} for item in body.prompts]

    return await image_gen_service.create(
        user_id=owner.user_id,
        job_id=job_uuid,
        prompts=prompts,
        api_key_override=resolved.api_key,
        api_base_override=resolved.api_base,
        endpoint_id_override=resolved.endpoint_id,
    )


@router.get("/image-gen")
async def list_image_gen_tasks(
    current_user: AuthUser,
    image_gen_service: ProductImageGenTaskUseCase = Depends(get_product_image_gen_task_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    job_id: Annotated[str | None, Query(description="按 job_id 筛选")] = None,
) -> dict[str, Any]:
    """8 图任务列表"""
    job_uuid = parse_optional_uuid(job_id, "job_id")
    items, total = await image_gen_service.list_tasks(skip=skip, limit=limit, job_id=job_uuid)
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/image-gen/providers")
async def get_image_gen_providers(
    image_gen_service: ProductImageGenTaskUseCase = Depends(get_product_image_gen_task_service),
) -> dict[str, Any]:
    """返回图像生成可用的 provider 列表及尺寸选项"""
    return image_gen_service.list_image_gen_providers()


@router.get("/image-gen/{task_id}")
async def get_image_gen_task(
    task_id: uuid.UUID,
    current_user: AuthUser,
    image_gen_service: ProductImageGenTaskUseCase = Depends(get_product_image_gen_task_service),
) -> dict[str, Any]:
    """8 图任务详情"""
    return await image_gen_service.get_task(task_id)


# =============================================================================
# 图片文件服务（本地存储）
# =============================================================================


@router.get("/images/{filename}")
async def serve_image(
    filename: str,
    image_service: ListingStudioImageService = Depends(get_listing_studio_image_service),
) -> FileResponse:
    """提供本地存储的图片（仅 storage_type=local）。"""
    path = await image_service.resolve_local_image_path(filename)
    if not path:
        raise NotFoundError("Image")
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    return FileResponse(path, media_type=media_type)
