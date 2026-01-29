"""
MCP Library - MCP 工具库

提供 MCP 相关的类型提示

注意：FastMCP 使用后，不再需要自定义的 MCPSession 类型，
工具函数直接使用 FastMCP 的装饰器定义。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MCPToolFunction(Protocol):
    """MCP 工具函数协议

    FastMCP 工具函数签名示例：
    ```python
    @server.tool()
    async def my_tool(arg1: str, arg2: int = 0) -> str: ...
    ```
    """

    async def __call__(
        self,
        **kwargs: Any,
    ) -> Any: ...


__all__ = ["MCPToolFunction"]
