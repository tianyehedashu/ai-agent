"""
MCP Server Infrastructure - MCP 服务器基础设施

使用 FastMCP 框架实现 MCP 服务器

包含:
- servers/: FastMCP 服务器实现（LLM Server 等）
- auth_middleware.py: API Key 认证中间件
"""

# 认证中间件导出
from domains.agent.infrastructure.mcp_server.auth_middleware import (
    get_required_scope_for_server,
    verify_mcp_access,
    verify_mcp_access_optional,
)

# FastMCP 服务器导出
from domains.agent.infrastructure.mcp_server.servers import (
    llm_create,
    llm_list_models,
    llm_server,
)

__all__ = [
    "get_required_scope_for_server",
    "llm_create",
    "llm_list_models",
    "llm_server",
    "verify_mcp_access",
    "verify_mcp_access_optional",
]
