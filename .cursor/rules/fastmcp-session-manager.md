# FastMCP session_manager 规则

**适用**: `mcp_server_router.py`, `main.py` 中 FastMCP 代码

FastMCP `session_manager` 必须先调用 `streamable_http_app()` 才能访问。

**正确**: 使用 `initialize_mcp_servers()` 上下文管理器
**禁止**: 直接访问 `SERVER_MAP[x].session_manager`

详见 `mcp_server_router.py` 模块文档。
