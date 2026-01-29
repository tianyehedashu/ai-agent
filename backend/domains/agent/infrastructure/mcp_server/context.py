"""
MCP Server Context - MCP 请求上下文

通过 contextvars 在 MCP 请求处理链中传递 user_id，
供 MCP 工具（如 LLM 调用）使用，以支持用户 Key 与配额。
"""

from contextvars import ContextVar, Token
from uuid import UUID

mcp_user_id_var: ContextVar[UUID | None] = ContextVar(
    "mcp_user_id",
    default=None,
)


def set_mcp_user_id(user_id: UUID | None) -> Token[UUID | None]:
    """设置当前 MCP 请求的 user_id，返回 token 用于 finally 中 reset"""
    return mcp_user_id_var.set(user_id)


def get_mcp_user_id() -> UUID | None:
    """获取当前 MCP 请求的 user_id（由路由在处理请求时设置）"""
    return mcp_user_id_var.get()
