"""
Tool API - 工具管理接口
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from models.user import User

router = APIRouter()


class ToolDefinition(BaseModel):
    """工具定义"""

    name: str
    description: str
    parameters: dict[str, Any]
    category: str
    requires_confirmation: bool


class ToolTestRequest(BaseModel):
    """工具测试请求"""

    arguments: dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolTestResponse(BaseModel):
    """工具测试响应"""

    success: bool
    result: Any
    error: str | None = None
    duration_ms: int


@router.get("/", response_model=list[ToolDefinition])
async def list_tools(
    current_user: User = Depends(get_current_user),
    category: str | None = None,
) -> list[ToolDefinition]:
    """获取可用工具列表"""
    from core.tool.registry import tool_registry

    tools = tool_registry.list_tools(category=category)
    return [
        ToolDefinition(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
            category=t.category,
            requires_confirmation=t.requires_confirmation,
        )
        for t in tools
    ]


@router.get("/{tool_name}", response_model=ToolDefinition)
async def get_tool(
    tool_name: str,
    current_user: User = Depends(get_current_user),
) -> ToolDefinition:
    """获取工具详情"""
    from core.tool.registry import tool_registry

    tool = tool_registry.get(tool_name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found",
        )

    return ToolDefinition(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters,
        category=tool.category,
        requires_confirmation=tool.requires_confirmation,
    )


@router.post("/{tool_name}/test", response_model=ToolTestResponse)
async def test_tool(
    tool_name: str,
    request: ToolTestRequest,
    current_user: User = Depends(get_current_user),
) -> ToolTestResponse:
    """测试工具执行"""
    import time

    from core.tool.executor import ToolExecutor
    from core.tool.registry import tool_registry

    tool = tool_registry.get(tool_name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found",
        )

    executor = ToolExecutor(registry=tool_registry)

    start_time = time.time()
    result = await executor.execute(
        name=tool_name,
        arguments=request.arguments,
        session_id=f"test_{current_user.id}",
    )
    duration_ms = int((time.time() - start_time) * 1000)

    return ToolTestResponse(
        success=result.success,
        result=result.output if result.success else None,
        error=result.error,
        duration_ms=duration_ms,
    )
