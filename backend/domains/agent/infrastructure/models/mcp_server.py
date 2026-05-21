"""
MCP Server Model - 用户/团队 MCP 服务器模型
"""

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TenantScopedMixin


class MCPServer(BaseModel, TenantScopedMixin):
    """用户级 MCP 服务器（归属 tenant_id）。

    ``tenant_id`` 由 ``TenantScopedMixin`` 提供（无 DB FK）。
    """

    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    env_type: Mapped[str] = mapped_column(String(50), nullable=False)
    env_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    template_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    inherit_defaults: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    connection_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_connected_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_tools: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<MCPServer {self.name} ({self.scope})>"
