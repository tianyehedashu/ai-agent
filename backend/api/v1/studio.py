"""
Studio API - 工作台 API

实现:
- 工作流 CRUD
- 代码解析
- 代码生成
- 测试运行
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from shared.presentation import VERSION_NOT_FOUND, WORKFLOW_NOT_FOUND, get_current_user
from domains.studio.infrastructure.studio.workflow import WorkflowService

router = APIRouter(prefix="/studio", tags=["Studio"])


# ============================================================================
# 请求/响应模型
# ============================================================================


class WorkflowCreateRequest(BaseModel):
    """创建工作流请求"""

    name: str
    description: str = ""
    code: str | None = None


class WorkflowUpdateRequest(BaseModel):
    """更新工作流请求"""

    name: str | None = None
    description: str | None = None
    code: str | None = None
    config: dict[str, Any] | None = None


class ParseCodeRequest(BaseModel):
    """解析代码请求"""

    code: str


class GenerateCodeRequest(BaseModel):
    """生成代码请求"""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class SaveVersionRequest(BaseModel):
    """保存版本请求"""

    message: str = ""


class TestRunRequest(BaseModel):
    """测试运行请求"""

    input_data: dict[str, Any]


# ============================================================================
# 工作流 CRUD API
# ============================================================================


@router.post("/workflows")
async def create_workflow(
    request: WorkflowCreateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """创建工作流"""
    service = WorkflowService()
    workflow = await service.create(
        name=request.name,
        description=request.description,
        user_id=current_user["id"],
        code=request.code,
    )
    return {
        "id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "code": workflow.code,
        "created_at": workflow.created_at.isoformat(),
    }


@router.get("/workflows")
async def list_workflows(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """列出工作流"""
    service = WorkflowService()
    workflows = await service.list_by_user(
        user_id=current_user["id"],
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "is_published": w.is_published,
            "created_at": w.created_at.isoformat(),
            "updated_at": w.updated_at.isoformat(),
        }
        for w in workflows
    ]


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """获取工作流详情"""
    service = WorkflowService()
    workflow = await service.get(workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail=WORKFLOW_NOT_FOUND)

    return {
        "id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "code": workflow.code,
        "config": workflow.config,
        "is_published": workflow.is_published,
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
    }


@router.put("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    request: WorkflowUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """更新工作流"""
    service = WorkflowService()
    workflow = await service.update(
        workflow_id=workflow_id,
        name=request.name,
        description=request.description,
        code=request.code,
        config=request.config,
    )

    if not workflow:
        raise HTTPException(status_code=404, detail=WORKFLOW_NOT_FOUND)

    return {
        "id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "code": workflow.code,
        "updated_at": workflow.updated_at.isoformat(),
    }


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """删除工作流"""
    service = WorkflowService()
    success = await service.delete(workflow_id)

    if not success:
        raise HTTPException(status_code=404, detail=WORKFLOW_NOT_FOUND)

    return {"status": "deleted"}


# ============================================================================
# Code-First API
# ============================================================================


@router.post("/workflows/{workflow_id}/parse")
async def parse_code(
    workflow_id: str,
    request: ParseCodeRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """解析代码，返回 React Flow 格式"""
    service = WorkflowService()
    return await service.parse_code(request.code)


@router.post("/workflows/{workflow_id}/generate")
async def generate_code(
    workflow_id: str,
    request: GenerateCodeRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """从 React Flow 格式生成代码"""
    service = WorkflowService()
    code = await service.generate_code(request.nodes, request.edges)
    return {"code": code}


# ============================================================================
# 版本管理 API
# ============================================================================


@router.post("/workflows/{workflow_id}/versions")
async def save_version(
    workflow_id: str,
    request: SaveVersionRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """保存新版本"""
    service = WorkflowService()
    version = await service.save_version(workflow_id, request.message)

    if not version:
        raise HTTPException(status_code=404, detail=WORKFLOW_NOT_FOUND)

    return {
        "id": str(version.id),
        "version": version.version,
        "message": version.message,
        "created_at": version.created_at.isoformat(),
    }


@router.get("/workflows/{workflow_id}/versions")
async def list_versions(
    workflow_id: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """列出版本历史"""
    service = WorkflowService()
    versions = await service.list_versions(workflow_id, limit)
    return [
        {
            "id": str(v.id),
            "version": v.version,
            "message": v.message,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]


@router.post("/workflows/{workflow_id}/versions/{version}/restore")
async def restore_version(
    workflow_id: str,
    version: int,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """恢复到指定版本"""
    service = WorkflowService()
    workflow = await service.restore_version(workflow_id, version)

    if not workflow:
        raise HTTPException(status_code=404, detail=VERSION_NOT_FOUND)

    return {
        "id": str(workflow.id),
        "code": workflow.code,
        "restored_version": version,
    }


# ============================================================================
# 测试运行 API
# ============================================================================


@router.post("/test/run")
async def test_run(
    request: TestRunRequest,
    workflow_id: str | None = None,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    测试运行工作流 (SSE)

    TODO: 实现实际的测试执行逻辑
    """

    async def event_generator():
        # 模拟执行事件
        events = [
            {"type": "started", "data": {"workflow_id": workflow_id}},
            {"type": "node_enter", "data": {"node": "process_input"}},
            {"type": "node_exit", "data": {"node": "process_input", "output": {}}},
            {"type": "node_enter", "data": {"node": "generate_response"}},
            {
                "type": "node_exit",
                "data": {"node": "generate_response", "output": {"response": "Hello!"}},
            },
            {"type": "completed", "data": {"result": {"response": "Hello!"}}},
        ]

        for event in events:
            yield f"data: {json.dumps(event)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
