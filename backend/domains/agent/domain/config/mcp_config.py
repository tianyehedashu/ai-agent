"""
MCP 服务器配置 - Domain 层类型定义

定义 MCP 服务器的配置类型，用于业务逻辑层
"""

from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, Field


class MCPEnvironmentType(str, Enum):
    """MCP 环境类型"""

    DYNAMIC_INJECTED = "dynamic_injected"  # 动态注入环境变量
    PREINSTALLED = "preinstalled"  # 预装依赖
    CUSTOM_IMAGE = "custom_image"  # 自定义镜像


class MCPScope(str, Enum):
    """MCP 服务器作用域"""

    SYSTEM = "system"  # 系统级（所有用户可见）
    USER = "user"  # 用户级（仅创建者可见）


class MCPServerEntityConfig(BaseModel):
    """MCP 服务器实体配置（Domain 层）"""

    id: uuid.UUID | None = Field(default=None, description="服务器 ID（创建时为空）")
    name: str = Field(..., description="服务器名称（唯一标识符）")
    display_name: str | None = Field(default=None, description="显示名称")
    url: str = Field(..., description="MCP 服务器 URL")
    scope: MCPScope = Field(..., description="作用域（system/user）")
    user_id: uuid.UUID | None = Field(default=None, description="创建者 ID（system 级为 NULL）")
    env_type: MCPEnvironmentType = Field(..., description="环境类型")
    env_config: dict[str, Any] = Field(default_factory=dict, description="环境配置")
    enabled: bool = Field(default=True, description="是否启用")

    class Config:
        from_attributes = True  # Pydantic v2


class MCPTemplate(BaseModel):
    """MCP 服务器模板"""

    id: str = Field(..., description="模板 ID")
    name: str = Field(..., description="服务器名称")
    display_name: str = Field(..., description="显示名称")
    description: str = Field(..., description="描述")
    category: str = Field(default="general", description="分类")
    icon: str = Field(default="server", description="图标")
    default_config: MCPServerEntityConfig = Field(..., description="默认配置")
    required_fields: list[str] = Field(default_factory=list, description="必填字段")
    optional_fields: list[str] = Field(default_factory=list, description="可选字段")
    field_labels: dict[str, str] = Field(default_factory=dict, description="字段标签")
    field_placeholders: dict[str, str] = Field(default_factory=dict, description="字段占位符")
    field_help_texts: dict[str, str] = Field(default_factory=dict, description="字段帮助文本")
