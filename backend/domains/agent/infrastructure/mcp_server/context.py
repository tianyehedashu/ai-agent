"""
MCP Server Context - MCP 请求上下文

通过 contextvars 在 MCP 请求处理链中传递 user_id 与 vendor_creator_id，
供 MCP 工具（如 LLM 调用、视频任务）使用，以支持用户 Key、配额及厂商侧创编者 ID。
"""

from contextvars import ContextVar, Token
from uuid import UUID

mcp_user_id_var: ContextVar[UUID | None] = ContextVar(
    "mcp_user_id",
    default=None,
)

mcp_vendor_creator_id_var: ContextVar[int | None] = ContextVar(
    "mcp_vendor_creator_id",
    default=None,
)


def set_mcp_user_id(user_id: UUID | None) -> Token[UUID | None]:
    """设置当前 MCP 请求的 user_id，返回 token 用于 finally 中 reset"""
    return mcp_user_id_var.set(user_id)


def get_mcp_user_id() -> UUID | None:
    """获取当前 MCP 请求的 user_id（由路由在处理请求时设置）"""
    return mcp_user_id_var.get()


def set_mcp_vendor_creator_id(vendor_creator_id: int | None) -> Token[int | None]:
    """设置当前 MCP 请求的 vendor_creator_id（由路由从 identity 层解析后设置）"""
    return mcp_vendor_creator_id_var.set(vendor_creator_id)


def get_mcp_vendor_creator_id() -> int | None:
    """获取当前 MCP 请求的 vendor_creator_id，供下游工具（如视频任务）与 Web 端行为一致"""
    return mcp_vendor_creator_id_var.get()
