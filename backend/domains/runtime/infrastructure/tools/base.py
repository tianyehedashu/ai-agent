"""
Tool Base - 工具基类

提供工具的基础实现和注册机制
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from shared.types import ToolCategory, ToolResult


class ToolParameters(BaseModel):
    """工具参数基类"""

    pass


class BaseTool(ABC):
    """
    工具基类

    所有工具必须继承此类并实现 execute 方法
    """

    # 工具元数据 (子类必须覆盖)
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    category: ClassVar[ToolCategory] = ToolCategory.SYSTEM
    requires_confirmation: ClassVar[bool] = False

    # 参数模型 (可选)
    parameters_model: ClassVar[type[ToolParameters] | None] = None

    @property
    def parameters(self) -> dict[str, Any]:
        """获取 JSON Schema 参数定义"""
        if self.parameters_model:
            return self.parameters_model.model_json_schema()
        return {"type": "object", "properties": {}}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具"""
        raise NotImplementedError

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_tool(self) -> dict[str, Any]:
        """转换为 Anthropic 工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


# 全局工具注册表
tool_registry: dict[str, type[BaseTool]] = {}


def register_tool(cls: type[BaseTool]) -> type[BaseTool]:
    """工具注册装饰器"""
    tool_registry[cls.name] = cls
    return cls
