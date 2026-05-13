"""
Product Info API - 产品信息工作流接口
"""

import asyncio
import mimetypes
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from domains.agent.application.product_image_gen_task_use_case import (
    ProductImageGenTaskUseCase,
)
from domains.agent.application.product_info_prompt_service import (
    ProductInfoPromptTemplateUseCase,
    get_default_prompt,
    list_capabilities,
    list_meta_prompt_params,
)
from domains.agent.application.product_info_use_case import (
    ProductInfoUseCase,
    run_pipeline_async,
)
from domains.agent.application.user_model_use_case import UserModelUseCase
from domains.identity.presentation.deps import AuthUser, get_owned_user_ids
from libs.api.deps import (
    get_product_image_gen_task_service,
    get_product_info_prompt_service,
    get_product_info_service,
    get_user_model_service,
)
from libs.api.params import parse_optional_uuid
from libs.background_tasks import register_app_background_task
from libs.exceptions import NotFoundError, ValidationError

router = APIRouter()


class RunStepBody(BaseModel):
    """执行单步请求体"""

    capability_id: str = Field(..., description="能力 ID")
    user_input: dict[str, Any] = Field(default_factory=dict)
    model_id: str | None = Field(None, description="用户模型 UUID 或系统模型 ID")
    meta_prompt: str | None = None
    prompt_template_id: str | None = None


class OptimizePromptBody(BaseModel):
    """提示词优化请求体（可选功能）"""

    capability_id: str = Field(..., description="能力 ID")
    user_input: dict[str, Any] = Field(default_factory=dict)
    meta_prompt: str | None = None
    model_id: str | None = Field(None, description="用户模型 UUID 或系统模型 ID")


class RunPipelineBody(BaseModel):
    """一键执行请求体"""

    inputs: dict[str, Any] = Field(default_factory=dict)
    steps: list[str] | None = None
    session_id: str | None = None


class CreateTemplateBody(BaseModel):
    """创建用户模板请求体"""

    name: str = Field(..., min_length=1, max_length=100)
    content: str | None = None
    prompts: list[str] | None = None


# =============================================================================
# Job 相关
# =============================================================================


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    current_user: AuthUser,
    service: ProductInfoUseCase = Depends(get_product_info_service),
    title: str | None = Query(None),
    session_id: str | None = Query(None),
) -> dict[str, Any]:
    """创建产品信息任务"""
    user_id, anonymous_user_id = get_owned_user_ids(current_user)
    session_uuid = parse_optional_uuid(session_id, "session_id")
    return await service.create_job(
        principal_id=current_user.id,
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
        session_id=session_uuid,
        title=title,
    )


@router.get("/jobs")
async def list_jobs(
    current_user: AuthUser,
    service: ProductInfoUseCase = Depends(get_product_info_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    session_id: str | None = None,
) -> dict[str, Any]:
    """产品信息任务列表"""
    session_uuid = parse_optional_uuid(session_id, "session_id")
    items, total = await service.list_jobs(
        skip=skip,
        limit=limit,
        status=status_filter,
        session_id=session_uuid,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    current_user: AuthUser,
    service: ProductInfoUseCase = Depends(get_product_info_service),
) -> dict[str, Any]:
    """任务详情（含 steps，用于后台查看）"""
    try:
        return await service.get_job(job_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    current_user: AuthUser,
    service: ProductInfoUseCase = Depends(get_product_info_service),
) -> None:
    """删除任务"""
    try:
        await service.delete_job(job_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# =============================================================================
# 执行某一步
# =============================================================================


@router.post("/jobs/{job_id}/steps")
async def run_step(
    job_id: uuid.UUID,
    body: RunStepBody,
    current_user: AuthUser,
    service: ProductInfoUseCase = Depends(get_product_info_service),
) -> dict[str, Any]:
    """执行工作流中的某一步：渲染提示词后直接执行"""
    template_uuid = None
    if body.prompt_template_id:
        try:
            template_uuid = uuid.UUID(body.prompt_template_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid prompt_template_id") from None
    try:
        return await service.run_step(
            job_id=job_id,
            capability_id=body.capability_id,
            user_input=body.user_input,
            meta_prompt=body.meta_prompt,
            prompt_template_id=template_uuid,
            model_id=body.model_id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/jobs/{job_id}/optimize-prompt")
async def optimize_prompt(
    job_id: uuid.UUID,
    body: OptimizePromptBody,
    current_user: AuthUser,
    service: ProductInfoUseCase = Depends(get_product_info_service),
) -> dict[str, Any]:
    """可选：AI 优化提示词，返回优化后的文本供用户确认"""
    try:
        optimized = await service.optimize_prompt(
            job_id=job_id,
            capability_id=body.capability_id,
            user_input=body.user_input,
            meta_prompt=body.meta_prompt,
            model_id=body.model_id,
        )
        return {"capability_id": body.capability_id, "optimized_prompt": optimized}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


# =============================================================================
# 能力与默认提示词
# =============================================================================


@router.get("/capabilities")
async def get_capabilities() -> list[dict[str, Any]]:
    """原子能力列表（无需认证）"""
    return list_capabilities()


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
    prompt_service: ProductInfoPromptTemplateUseCase = Depends(get_product_info_prompt_service),
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
    prompt_service: ProductInfoPromptTemplateUseCase = Depends(get_product_info_prompt_service),
) -> dict[str, Any]:
    """保存为用户模板"""
    user_id, anonymous_user_id = get_owned_user_ids(current_user)
    return await prompt_service.create_template(
        capability_id=capability_id,
        name=body.name,
        content=body.content,
        prompts=body.prompts,
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
    )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: uuid.UUID,
    current_user: AuthUser,
    prompt_service: ProductInfoPromptTemplateUseCase = Depends(get_product_info_prompt_service),
) -> dict[str, Any]:
    """获取单条模板"""
    try:
        return await prompt_service.get_template(template_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


class UpdateTemplateBody(BaseModel):
    """更新用户模板请求体"""

    name: str | None = Field(None, min_length=1, max_length=100)
    content: str | None = None
    prompts: list[str] | None = None


class CreateImageGenTaskBody(BaseModel):
    """创建 8 图任务请求体

    model_id: 系统模型 ID (如 "volcengine/seedream") 或用户模型 UUID。
    全局字段（provider / size / reference_image_url / strength）会自动合并到
    每条 prompt item 中（item 自身的同名字段优先），简化前端调用。
    """

    prompts: list[dict[str, Any]] = Field(default_factory=list)
    job_id: str | None = None
    model_id: str | None = None
    provider: str | None = None
    size: str | None = None
    reference_image_url: str | None = None
    strength: float | None = None


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: uuid.UUID,
    body: UpdateTemplateBody,
    current_user: AuthUser,
    prompt_service: ProductInfoPromptTemplateUseCase = Depends(get_product_info_prompt_service),
) -> dict[str, Any]:
    """更新用户模板"""
    try:
        return await prompt_service.update_template(
            template_id,
            name=body.name,
            content=body.content,
            prompts=body.prompts,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    current_user: AuthUser,
    prompt_service: ProductInfoPromptTemplateUseCase = Depends(get_product_info_prompt_service),
) -> None:
    """删除用户模板"""
    try:
        await prompt_service.delete_template(template_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# =============================================================================
# 一键异步执行
# =============================================================================


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_pipeline(
    request: Request,
    current_user: AuthUser,
    service: ProductInfoUseCase = Depends(get_product_info_service),
    body: RunPipelineBody | None = None,
) -> dict[str, Any]:
    """
    一键异步执行：创建 Job，在后台按顺序执行各步，立即返回 job_id。
    客户端通过 GET /jobs/{job_id} 后台查看进度与结果。
    """
    if body is None:
        body = RunPipelineBody()
    user_id, anonymous_user_id = get_owned_user_ids(current_user)
    session_uuid = parse_optional_uuid(body.session_id, "session_id")

    job = await service.create_job(
        principal_id=current_user.id,
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
        session_id=session_uuid,
        title="一键执行",
        status="running",
    )
    job_id = job["id"]

    pipeline_bg_task = asyncio.create_task(
        run_pipeline_async(
            job_id=uuid.UUID(job_id),
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            inputs=body.inputs or {},
            steps=body.steps,
        )
    )
    pipeline_bg_task.set_name(f"product-info-pipeline:{job_id}")
    register_app_background_task(request.app, pipeline_bg_task)

    return {
        "job_id": job_id,
        "status": "running",
        "message": "任务已提交，请使用 job_id 在后台查看进度与结果。",
        "poll_url": f"/api/v1/product-info/jobs/{job_id}",
    }


# =============================================================================
# 图片上传（占位：返回可访问 URL，后续接入对象存储）
# =============================================================================


@router.post("/upload")
async def upload_image(
    current_user: AuthUser,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    上传图片，返回 URL 供输入区与历史预览使用。
    当前为占位实现，返回固定前缀 URL；后续可接入对象存储。
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    # 占位：实际应落盘或上传至对象存储后返回真实 URL
    url = f"https://placeholder/product-info/{file.filename or 'image'}"
    return {
        "url": url,
        "content_type": file.content_type,
        "size_bytes": 0,
    }


# =============================================================================
# 8 图生成任务（创建后异步调用 ImageGenerator 生成图片）
# =============================================================================


@router.post("/image-gen", status_code=status.HTTP_201_CREATED)
async def create_image_gen_task(
    current_user: AuthUser,
    image_gen_service: ProductImageGenTaskUseCase = Depends(get_product_image_gen_task_service),
    user_model_service: UserModelUseCase = Depends(get_user_model_service),
    body: CreateImageGenTaskBody | None = None,
) -> dict[str, Any]:
    """创建 8 图生成任务。

    model_id 可以是系统模型 (如 "volcengine/seedream") 或用户模型 UUID，
    通过 UserModelUseCase 解析为 provider + credentials。
    """
    if body is None:
        body = CreateImageGenTaskBody()
    user_id, anonymous_user_id = get_owned_user_ids(current_user)
    job_uuid = parse_optional_uuid(body.job_id, "job_id")

    resolved = await user_model_service.resolve_image_gen_model(body.model_id)

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
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
        job_id=job_uuid,
        prompts=prompts,
        api_key_override=resolved.api_key,
        api_base_override=resolved.api_base,
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
async def get_image_gen_providers() -> dict[str, Any]:
    """返回图像生成可用的 provider 列表及尺寸选项"""
    from domains.agent.infrastructure.llm.image_generator import (  # pylint: disable=import-outside-toplevel
        PROVIDER_DEFAULTS,
        PROVIDER_SIZE_OPTIONS,
        SUPPORTED_PROVIDERS,
    )

    providers = []
    for pid in SUPPORTED_PROVIDERS:
        defaults = PROVIDER_DEFAULTS.get(pid, {})
        providers.append(
            {
                "id": pid,
                "name": {"volcengine": "火山引擎 Seedream", "openai": "OpenAI DALL-E 3"}.get(
                    pid, pid
                ),
                "default_size": defaults.get("size", "1024x1024"),
                "sizes": PROVIDER_SIZE_OPTIONS.get(pid, []),
                "supports_reference_image": True,
            }
        )
    return {"providers": providers}


@router.get("/image-gen/{task_id}")
async def get_image_gen_task(
    task_id: uuid.UUID,
    current_user: AuthUser,
    image_gen_service: ProductImageGenTaskUseCase = Depends(get_product_image_gen_task_service),
) -> dict[str, Any]:
    """8 图任务详情"""
    try:
        return await image_gen_service.get_task(task_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Image gen task not found") from None


# =============================================================================
# 图片文件服务（本地存储）
# =============================================================================


@router.get("/images/{filename}")
async def serve_image(filename: str) -> FileResponse:
    """提供本地存储的生成图片"""
    from libs.storage.local_image_store import (
        get_image_path,  # pylint: disable=import-outside-toplevel
    )

    path = get_image_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Image not found")
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    return FileResponse(path, media_type=media_type)
