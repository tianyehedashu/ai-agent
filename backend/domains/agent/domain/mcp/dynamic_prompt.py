"""
MCP 动态 Prompt - 领域类型

用于「可添加 Prompt 模板」的 MCP（客户端直连 Streamable HTTP、后续 DB MCP）。
arguments_schema 与 MCP PromptArgument 对齐：name, description, required。
"""

from typing import Any

from pydantic import BaseModel, Field


class PromptArgumentSpec(BaseModel):
    """单个 Prompt 参数规格（与 MCP PromptArgument 对齐）"""

    name: str = Field(..., description="参数名")
    description: str | None = Field(default=None, description="参数描述")
    required: bool = Field(default=True, description="是否必填")


class DynamicPromptEntity(BaseModel):
    """动态 Prompt 领域实体（与存储解耦）"""

    id: str | None = None
    server_kind: str = Field(..., description="streamable_http | db_server")
    server_id: str = Field(..., description="server_name or server UUID")
    prompt_key: str = Field(..., description="Prompt 唯一键，同 server 内唯一")
    title: str | None = None
    description: str | None = None
    arguments_schema: list[dict[str, Any]] = Field(
        default_factory=list,
        description='[{"name":"x","description":"...","required":true}]',
    )
    template: str = Field(..., description="提示词模板，占位符 {{name}}")
    enabled: bool = True

    class Config:
        from_attributes = True
