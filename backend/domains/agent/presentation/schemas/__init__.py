"""
Presentation Schemas

API 请求和响应的数据模型
"""

from domains.agent.presentation.schemas.mcp_schemas import (
    MCPServerCreateRequest,
    MCPServerResponse,
    MCPServersListResponse,
    MCPServerUpdateRequest,
    MCPTemplateResponse,
    MCPTestResult,
)

__all__ = [
    "MCPServerCreateRequest",
    "MCPServerResponse",
    "MCPServerUpdateRequest",
    "MCPServersListResponse",
    "MCPTemplateResponse",
    "MCPTestResult",
]
