"""
MCP Dynamic Tool Model - MCP 动态工具模型

存储按 server 维度的可添加工具（客户端直连 MCP 的 server_name，或 DB MCP 的 server_id）。
"""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class MCPDynamicTool(BaseModel):
    """MCP 动态工具模型"""

    __tablename__ = "mcp_dynamic_tools"
    __table_args__ = (
        UniqueConstraint(
            "server_kind", "server_id", "tool_key", name="uq_mcp_dynamic_tools_server_tool"
        ),
    )

    server_kind: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="streamable_http | db_server"
    )
    server_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="server_name or server UUID"
    )
    tool_key: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )

    def __repr__(self) -> str:
        return f"<MCPDynamicTool {self.server_kind}:{self.server_id}/{self.tool_key}>"
