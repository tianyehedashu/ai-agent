"""
MCP API 数据模型（Application 层）

供 MCPManagementUseCase 与 Presentation 共用，避免 Application 依赖 presentation。
"""

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field, computed_field, field_serializer

from domains.agent.domain.config.mcp_config import MCPEnvironmentType

__all__ = [
    "MCPServerCreateRequest",
    "MCPServerResponse",
    "MCPServerUpdateRequest",
    "MCPServersListResponse",
    "MCPTemplateResponse",
    "MCPTestResult",
    "MCPToolInfo",
    "MCPToolToggleRequest",
    "MCPToolsListResponse",
]


class MCPTemplateResponse(BaseModel):
    """MCP 服务器模板响应"""

    id: str
    name: str
    display_name: str
    description: str
    category: str
    icon: str
    required_fields: list[str]
    optional_fields: list[str]
    field_labels: dict[str, str]
    field_placeholders: dict[str, str]
    field_help_texts: dict[str, str]


class MCPServerResponse(BaseModel):
    """MCP 服务器响应"""

    id: uuid.UUID
    name: str
    display_name: str | None
    url: str
    scope: str  # 'system' | 'user'
    env_type: str
    env_config: dict[str, Any]
    enabled: bool
    connection_status: str | None = None
    last_connected_at: str | None = None
    last_error: str | None = None
    available_tools: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    user_id: uuid.UUID | None = Field(
        default=None,
        description="API 展示用：用户级 MCP 的创建者；系统级为 None",
    )
    template_id: str | None = None
    inherit_defaults: bool = False

    @computed_field
    @property
    def overall_status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.connection_status == "connected":
            return "connected"
        if self.connection_status == "failed":
            return "failed"
        return "unknown"

    @computed_field
    @property
    def status_color(self) -> str:
        color_map = {
            "disabled": "gray",
            "connected": "green",
            "failed": "red",
            "unknown": "yellow",
        }
        return color_map.get(self.overall_status, "gray")

    @computed_field
    @property
    def status_text(self) -> str:
        text_map = {
            "disabled": "已禁用",
            "connected": "已连接",
            "failed": "连接失败",
            "unknown": "未测试",
        }
        return text_map.get(self.overall_status, "未知")

    class Config:
        from_attributes = True

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else ""


class MCPServersListResponse(BaseModel):
    system_servers: list[MCPServerResponse]
    user_servers: list[MCPServerResponse]


class MCPServerCreateRequest(BaseModel):
    template_id: str | None = Field(None, description="模板 ID（可选，用于从模板创建）")
    name: str = Field(..., description="服务器名称（唯一标识符）")
    display_name: str | None = Field(None, description="显示名称")
    url: str = Field(..., description="MCP 服务器 URL")
    env_type: MCPEnvironmentType = Field(..., description="环境类型")
    env_config: dict[str, Any] = Field(default_factory=dict, description="环境配置")
    enabled: bool = Field(True, description="是否启用")
    inherit_defaults: bool = Field(False, description="是否继承模板默认配置（可选同步）")


class MCPServerUpdateRequest(BaseModel):
    display_name: str | None = Field(None, description="显示名称")
    url: str | None = Field(None, description="MCP 服务器 URL")
    env_type: MCPEnvironmentType | None = Field(None, description="环境类型")
    env_config: dict[str, Any] | None = Field(None, description="环境配置")
    enabled: bool | None = Field(None, description="是否启用")
    inherit_defaults: bool | None = Field(None, description="是否继承模板默认配置（可选同步）")


class MCPTestResult(BaseModel):
    success: bool
    message: str
    server_name: str
    server_url: str
    connection_status: str | None = None
    error_details: str | None = None
    tools_count: int = 0
    tools_sample: list[str] = Field(default_factory=list)


class MCPToolInfo(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    token_count: int = 0


class MCPToolsListResponse(BaseModel):
    server_id: uuid.UUID
    server_name: str
    tools: list[MCPToolInfo]
    total_tokens: int = 0
    enabled_count: int = 0


class MCPToolToggleRequest(BaseModel):
    enabled: bool = Field(..., description="是否启用该工具")
