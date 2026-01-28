"""
MCP Router - MCP 管理 API 路由

提供 MCP 服务器的管理接口
"""

import uuid

from fastapi import APIRouter, Depends, status

from domains.agent.application.mcp_use_case import MCPManagementUseCase
from domains.agent.presentation.schemas.mcp_schemas import (
    MCPServerCreateRequest,
    MCPServerResponse,
    MCPServersListResponse,
    MCPServerUpdateRequest,
    MCPTemplateResponse,
    MCPTestResult,
    MCPToolInfo,
    MCPToolsListResponse,
    MCPToolToggleRequest,
)
from domains.identity.presentation.deps import AuthUser, RequiredAuthUser
from libs.api.deps import get_mcp_service

router = APIRouter()


@router.get(
    "/templates",
    summary="列出 MCP 服务器模板",
)
async def list_templates(
    current_user: AuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> list[MCPTemplateResponse]:
    """列出所有可用的 MCP 服务器模板"""
    templates = await use_case.list_templates()
    return [
        MCPTemplateResponse(
            id=t.id,
            name=t.name,
            display_name=t.display_name,
            description=t.description,
            category=t.category,
            icon=t.icon,
            required_fields=t.required_fields,
            optional_fields=t.optional_fields,
            field_labels=t.field_labels,
            field_placeholders=t.field_placeholders,
            field_help_texts=t.field_help_texts,
        )
        for t in templates
    ]


@router.get(
    "/servers",
    summary="列出 MCP 服务器",
)
async def list_servers(
    current_user: AuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPServersListResponse:
    """列出可用的 MCP 服务器（system + user）"""
    return await use_case.list_servers(current_user)


@router.post(
    "/servers",
    status_code=status.HTTP_201_CREATED,
    summary="添加 MCP 服务器",
)
async def add_server(
    request: MCPServerCreateRequest,
    current_user: RequiredAuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPServerResponse:
    """添加新的 MCP 服务器"""
    server = await use_case.add_server(request, current_user)
    return MCPServerResponse.model_validate(server)


@router.put(
    "/servers/{server_id}",
    summary="更新 MCP 服务器",
)
async def update_server(
    server_id: uuid.UUID,
    request: MCPServerUpdateRequest,
    current_user: RequiredAuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPServerResponse:
    """更新 MCP 服务器配置"""
    server = await use_case.update_server(server_id, request, current_user)
    return MCPServerResponse.model_validate(server)


@router.delete(
    "/servers/{server_id}",
    summary="删除 MCP 服务器",
)
async def delete_server(
    server_id: uuid.UUID,
    current_user: RequiredAuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> dict[str, str]:
    """删除 MCP 服务器"""
    await use_case.delete_server(server_id, current_user)
    return {"message": "Server deleted successfully"}


@router.patch(
    "/servers/{server_id}/toggle",
    summary="切换 MCP 服务器状态",
)
async def toggle_server(
    server_id: uuid.UUID,
    enabled: bool,
    current_user: RequiredAuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPServerResponse:
    """启用或禁用 MCP 服务器"""
    server = await use_case.toggle_server(server_id, enabled, current_user)
    return MCPServerResponse.model_validate(server)


@router.post(
    "/servers/{server_id}/test",
    summary="测试 MCP 服务器连接",
)
async def test_connection(
    server_id: uuid.UUID,
    current_user: AuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPTestResult:
    """测试 MCP 服务器的连接状态"""
    result = await use_case.test_connection(server_id, current_user)
    return MCPTestResult(**result)


@router.get(
    "/servers/{server_id}/tools",
    summary="获取 MCP 服务器的工具列表",
)
async def list_server_tools(
    server_id: uuid.UUID,
    current_user: AuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPToolsListResponse:
    """获取 MCP 服务器的工具列表及 Token 占用"""
    return await use_case.list_server_tools(server_id, current_user)


@router.put(
    "/servers/{server_id}/tools/{tool_name}/enabled",
    summary="切换工具启用状态",
)
async def toggle_tool_enabled(
    server_id: uuid.UUID,
    tool_name: str,
    request: MCPToolToggleRequest,
    current_user: RequiredAuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPToolInfo:
    """启用或禁用特定工具"""
    return await use_case.toggle_tool_enabled(server_id, tool_name, request.enabled, current_user)
