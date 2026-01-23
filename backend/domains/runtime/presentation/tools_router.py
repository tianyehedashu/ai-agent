"""
Tools Router - 工具路由

提供工具相关API 端点
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from shared.types import ToolCategory
from domains.runtime.infrastructure.tools.registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["Tools"])


# =============================================================================
# 请求/响应模型
# =============================================================================


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


# =============================================================================
# 辅助函数
# =============================================================================


def _get_registry() -> ToolRegistry:
    """获取工具注册""
    return ToolRegistry()


# =============================================================================
# API 端点
# =============================================================================


@router.get("/", response_model=list[ToolDefinition])
async def list_tools(
    category: str | None = None,
) -> list[ToolDefinition]:
    """获取可用工具列表"""
    registry = _get_registry()

    if category:
        try:
            cat = ToolCategory(category)
            tools = registry.list_by_category(cat)
        except ValueError:
            tools = []
    else:
        tools = registry.list_all()

    return [
        ToolDefinition(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
            category=t.category.value if hasattr(t.category, "value") else str(t.category),
            requires_confirmation=t.requires_confirmation,
        )
        for t in tools
    ]


@router.get("/{tool_name}", response_model=ToolDefinition)
async def get_tool(tool_name: str) -> ToolDefinition:
    """获取工具详情"""
    registry = _get_registry()
    tool = registry.get(tool_name)

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found",
        )

    return ToolDefinition(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters,
        category=tool.category.value if hasattr(tool.category, "value") else str(tool.category),
        requires_confirmation=tool.requires_confirmation,
    )


@router.post("/{tool_name}/test", response_model=ToolTestResponse)
async def test_tool(
    tool_name: str,
    request: ToolTestRequest,
) -> ToolTestResponse:
    """测试工具执行"""
    registry = _get_registry()
    tool = registry.get(tool_name)

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found",
        )

    start_time = time.time()
    result = await registry.execute(
        name=tool_name,
        **request.arguments,
    )
    duration_ms = int((time.time() - start_time) * 1000)

    return ToolTestResponse(
        success=result.success,
        result=result.output if result.success else None,
        error=result.error,
        duration_ms=duration_ms,
    )
