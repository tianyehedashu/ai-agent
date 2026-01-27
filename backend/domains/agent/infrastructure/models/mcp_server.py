"""
MCP Server Model - MCP 服务器模型
"""

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, OwnedMixin


class MCPServer(BaseModel, OwnedMixin):
    """MCP 服务器模型

    继承 OwnedMixin 提供所有权相关的类型协议和方法。
    支持系统级（user_id=NULL）和用户级（user_id 设置）服务器。

    注意：不使用数据库外键约束，仅通过应用层权限控制。
    """

    __tablename__ = "mcp_servers"

    # 所有权字段（不使用外键）
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="所有者用户ID，NULL表示系统级服务器",
    )

    # 基本字段
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 服务器配置
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user"
    )  # 'system' | 'user'

    # 环境配置
    env_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 环境类型
    env_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # 环境配置

    # 状态
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 连接状态
    connection_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="连接状态: connected, failed, unknown"
    )
    last_connected_at: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="最后连接时间 (ISO格式)"
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="最后错误信息"
    )
    available_tools: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="可用工具列表"
    )

    # 元数据
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 时间戳（由 BaseModel 提供）
    # created_at, updated_at

    def __repr__(self) -> str:
        return f"<MCPServer {self.name} ({self.scope})>"
