"""MCP 服务器访问策略（纯函数，不依赖 ORM / HTTP）。"""

from __future__ import annotations

from enum import Enum

from libs.exceptions import PermissionDeniedError


class McpServerKind(str, Enum):
    SYSTEM = "system"
    USER = "user"


class McpAccessAction(str, Enum):
    """对 MCP 资源的操作类型。"""

    READ_TOOLS = "read_tools"
    MUTATE = "mutate"
    MUTATE_SYSTEM_TOOLS = "mutate_system_tools"


_DENIAL_CODES: dict[tuple[McpServerKind, McpAccessAction], str] = {
    (McpServerKind.SYSTEM, McpAccessAction.MUTATE): "CANNOT_UPDATE_SYSTEM_SERVER",
    (McpServerKind.SYSTEM, McpAccessAction.MUTATE_SYSTEM_TOOLS): "CANNOT_MODIFY_SYSTEM_SERVER",
}


def mcp_server_kind(*, is_system: bool) -> McpServerKind:
    return McpServerKind.SYSTEM if is_system else McpServerKind.USER


def assert_mcp_access(
    *,
    kind: McpServerKind,
    is_platform_admin: bool,
    action: McpAccessAction,
) -> None:
    """校验主体是否可对指定类型 MCP 执行操作；失败抛出 PermissionDeniedError。"""
    if kind is McpServerKind.USER:
        return
    if action is McpAccessAction.READ_TOOLS:
        return
    if is_platform_admin:
        return
    code = _DENIAL_CODES.get((kind, action), "PERMISSION_DENIED")
    messages = {
        "CANNOT_UPDATE_SYSTEM_SERVER": "Cannot update system server",
        "CANNOT_MODIFY_SYSTEM_SERVER": "Cannot modify system server tools",
        "PERMISSION_DENIED": "Permission denied",
    }
    raise PermissionDeniedError(messages.get(code, "Permission denied"), code=code)


def assert_mcp_delete(*, kind: McpServerKind, is_platform_admin: bool) -> None:
    if kind is McpServerKind.USER or is_platform_admin:
        return
    raise PermissionDeniedError(
        "Cannot delete system server",
        code="CANNOT_DELETE_SYSTEM_SERVER",
    )


__all__ = [
    "McpAccessAction",
    "McpServerKind",
    "assert_mcp_access",
    "assert_mcp_delete",
    "mcp_server_kind",
]
