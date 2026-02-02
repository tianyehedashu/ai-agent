"""
MCP Dynamic Prompt Model - MCP 动态 Prompt 模型

存储按 server 维度的可添加 prompt 模板（客户端直连 MCP 的 server_name，或 DB MCP 的 server_id）。
"""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel


class MCPDynamicPrompt(BaseModel):
    """MCP 动态 Prompt 模型"""

    __tablename__ = "mcp_dynamic_prompts"
    __table_args__ = (
        UniqueConstraint(
            "server_kind",
            "server_id",
            "prompt_key",
            name="uq_mcp_dynamic_prompts_server_prompt",
        ),
    )

    server_kind: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="streamable_http | db_server"
    )
    server_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="server_name or server UUID"
    )
    prompt_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    arguments_schema: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    template: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )

    def __repr__(self) -> str:
        return f"<MCPDynamicPrompt {self.server_kind}:{self.server_id}/{self.prompt_key}>"
