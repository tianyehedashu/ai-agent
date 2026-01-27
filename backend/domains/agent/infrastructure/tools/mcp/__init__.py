"""
MCP (Model Context Protocol) 协议支持

支持通过 MCP 协议集成第三方工具和服务
"""

from domains.agent.infrastructure.tools.mcp.adapter import MCPAdapter
from domains.agent.infrastructure.tools.mcp.client import (
    ConfiguredMCPManager,
    MCPClient,
)
from domains.agent.infrastructure.tools.mcp.tool_service import MCPToolService
from domains.agent.infrastructure.tools.mcp.wrapper import MCPToolWrapper

__all__ = [
    "ConfiguredMCPManager",
    "MCPAdapter",
    "MCPClient",
    "MCPToolService",
    "MCPToolWrapper",
]
