"""
MCP Server Domain - MCP 服务器领域

包含:
- scopes: MCP 服务器作用域定义
"""

# 领域导出
from domains.agent.domain.mcp.scopes import MCPServerScope

__all__ = [
    # Scopes
    "MCPServerScope",
]
