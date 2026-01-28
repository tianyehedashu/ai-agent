"""
MCP Schemas - MCP API 请求/响应模式

定义 MCP 管理相关的 API 数据结构
"""

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field, computed_field, field_serializer

from domains.agent.domain.config.mcp_config import MCPEnvironmentType


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
    connection_status: str | None = None  # connected, failed, unknown
    last_connected_at: str | None = None  # ISO 格式时间字符串
    last_error: str | None = None
    available_tools: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    user_id: uuid.UUID | None = None

    # 综合状态（前端用于颜色显示）
    @computed_field
    @property
    def overall_status(self) -> str:
        """
        综合状态（考虑 enabled 和 connection_status）

        Returns:
            disabled: 服务器已禁用（灰色）
            connected: 服务器已连接（绿色）
            failed: 连接失败（红色）
            unknown: 未测试（黄色）
        """
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
        """
        状态颜色（前端用于显示）

        Returns:
            gray: 灰色（禁用）
            green: 绿色（已连接）
            red: 红色（连接失败）
            yellow: 黄色（未测试）
        """
        status = self.overall_status
        color_map = {
            "disabled": "gray",
            "connected": "green",
            "failed": "red",
            "unknown": "yellow",
        }
        return color_map.get(status, "gray")

    @computed_field
    @property
    def status_text(self) -> str:
        """
        状态文本（前端用于显示）

        Returns:
            用户友好的状态描述
        """
        status = self.overall_status
        text_map = {
            "disabled": "已禁用",
            "connected": "已连接",
            "failed": "连接失败",
            "unknown": "未测试",
        }
        return text_map.get(status, "未知")

    class Config:
        from_attributes = True

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime) -> str:
        """序列化 datetime 为 ISO 格式字符串"""
        return dt.isoformat() if dt else ""


class MCPServersListResponse(BaseModel):
    """MCP 服务器列表响应"""

    system_servers: list[MCPServerResponse]
    user_servers: list[MCPServerResponse]


class MCPServerCreateRequest(BaseModel):
    """创建 MCP 服务器请求"""

    template_id: str | None = Field(
        None, description="模板 ID（可选，用于从模板创建）"
    )
    name: str = Field(..., description="服务器名称（唯一标识符）")
    display_name: str | None = Field(None, description="显示名称")
    url: str = Field(..., description="MCP 服务器 URL")
    env_type: MCPEnvironmentType = Field(..., description="环境类型")
    env_config: dict[str, Any] = Field(
        default_factory=dict, description="环境配置"
    )
    enabled: bool = Field(True, description="是否启用")


class MCPServerUpdateRequest(BaseModel):
    """更新 MCP 服务器请求"""

    display_name: str | None = Field(None, description="显示名称")
    url: str | None = Field(None, description="MCP 服务器 URL")
    env_type: MCPEnvironmentType | None = Field(None, description="环境类型")
    env_config: dict[str, Any] | None = Field(None, description="环境配置")
    enabled: bool | None = Field(None, description="是否启用")


class MCPTestResult(BaseModel):
    """MCP 连接测试结果"""

    success: bool
    message: str
    server_name: str
    server_url: str
    connection_status: str | None = None  # connected, failed, unknown
    error_details: str | None = None
    tools_count: int = 0  # 可用工具数量
    tools_sample: list[str] = Field(default_factory=list)  # 部分工具名称示例


class MCPToolInfo(BaseModel):
    """MCP 工具信息"""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    token_count: int = 0


class MCPToolsListResponse(BaseModel):
    """MCP 工具列表响应"""

    server_id: uuid.UUID
    server_name: str
    tools: list[MCPToolInfo]
    total_tokens: int = 0
    enabled_count: int = 0


class MCPToolToggleRequest(BaseModel):
    """工具启用/禁用请求"""

    enabled: bool = Field(..., description="是否启用该工具")
