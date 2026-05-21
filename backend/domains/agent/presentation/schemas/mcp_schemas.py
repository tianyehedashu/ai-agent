"""
MCP Schemas - MCP API 请求/响应模式

从 Application 层再导出，保持 Presentation 导入路径稳定。
"""

from domains.agent.application.mcp_api_models import (
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
from domains.agent.application.mcp_server_mapper import mcp_server_to_response

__all__ = [
    "MCPServerCreateRequest",
    "MCPServerResponse",
    "MCPServerUpdateRequest",
    "MCPServersListResponse",
    "MCPTemplateResponse",
    "MCPTestResult",
    "MCPToolInfo",
    "MCPToolToggleRequest",
    "MCPToolsListResponse",
    "mcp_server_to_response",
]
