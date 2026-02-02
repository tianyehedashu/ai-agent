"""
MCP 动态工具 - 领域类型与枚举

用于「可添加工具」的 MCP（客户端直连 Streamable HTTP、后续 DB MCP）。
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DynamicToolType(str, Enum):
    """预定义动态工具类型"""

    HTTP_CALL = "http_call"
    # INTERNAL_API = "internal_api"  # 可选二期


class DynamicToolEntity(BaseModel):
    """动态工具领域实体（与存储解耦）"""

    id: str | None = None
    server_kind: str = Field(..., description="streamable_http | db_server")
    server_id: str = Field(..., description="server_name or server UUID")
    tool_key: str = Field(..., description="工具唯一键，同 server 内唯一")
    tool_type: str = Field(..., description="DynamicToolType.value")
    config: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    enabled: bool = True

    class Config:
        from_attributes = True
