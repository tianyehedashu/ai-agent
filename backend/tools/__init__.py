"""
Tool System - 工具系统

提供 Agent 可调用的工具集合
"""

# 导入工具模块以触发注册
from tools import code_tools, file_tools, search_tools
from tools.base import BaseTool, register_tool, tool_registry
from tools.registry import ToolRegistry

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "code_tools",
    "file_tools",
    "register_tool",
    "search_tools",
    "tool_registry",
]
