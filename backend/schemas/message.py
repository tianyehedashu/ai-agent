"""
Message Schemas - 消息相关 Schema

提供对话事件、工具调用等数据结构。
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from utils.serialization import SerializableDict, Serializer


class ChatEvent(BaseModel):
    """对话事件

    用于 SSE 流式传输的事件数据。

    Attributes:
        type: 事件类型 (thinking, text, tool_call, tool_result, interrupt, done, error)
        data: 事件数据
        timestamp: 事件时间戳
    """

    model_config = ConfigDict(
        frozen=True,
        # 移除 ser_json_infra=True，避免 Pydantic 内部序列化检查导致警告
        # ser_json_infra=True,  # 注释掉，看看是否能解决问题
    )

    type: str
    # 使用 SerializableDict 类型，既保持类型安全，又提供运行时验证
    data: SerializableDict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="before")
    @classmethod
    def validate_all_data(cls, data: Any) -> Any:
        """在模型验证之前，深度序列化所有数据，确保 LiteLLM 对象被转换"""
        if isinstance(data, dict) and "data" in data:
            data["data"] = (
                Serializer.serialize_dict(data["data"])
                if isinstance(data["data"], dict)
                else Serializer.serialize(data["data"])
            )
        return data

    @model_serializer(mode="wrap")
    def serialize_model(self, serializer: Any, info: Any) -> dict[str, Any]:
        """自定义序列化，确保所有嵌套对象都被正确序列化"""
        # 先使用默认序列化
        result = serializer(self)

        # 然后深度序列化 data 字段，确保 LiteLLM 对象被转换
        if isinstance(result, dict) and "data" in result:
            result["data"] = Serializer.serialize_dict(result["data"])
        return result


class ToolCallData(BaseModel):
    """工具调用数据"""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResultData(BaseModel):
    """工具结果数据"""

    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    success: bool
    output: str
    error: str | None = None


class InterruptData(BaseModel):
    """中断数据

    Human-in-the-Loop 场景下的中断信息。
    """

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    pending_action: ToolCallData
    reason: str
