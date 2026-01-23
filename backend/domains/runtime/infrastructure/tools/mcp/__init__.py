"""
MCP (Model Context Protocol) 协议支持

支持通过 MCP 协议集成第三方工具和服务
"""

from domains.runtime.infrastructure.tools.mcp.adapter import MCPAdapter
from domains.runtime.infrastructure.tools.mcp.client import MCPClient

__all__ = [
    "MCPAdapter",
    "MCPClient",
]
