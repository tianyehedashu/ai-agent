"""
Serialization Utilities - 序列化工具

提供统一的序列化工具，确保所有对象都能被正确序列化为 JSON 兼容格式。

设计原则：
1. 类型安全：使用明确的类型定义，支持静态类型检查
2. 运行时验证：通过 Pydantic 验证器确保数据正确性
3. 性能优化：避免不必要的深度验证，只在必要时进行序列化
4. 灵活性：支持扩展字段，不丢失有用信息
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from pydantic import BaseModel, PlainValidator

logger = logging.getLogger(__name__)

# JSON 兼容的基本类型定义
# 使用 Union 类型而不是递归类型别名，避免 Pydantic schema 生成时的递归问题
# 同时保持类型检查时的类型安全
JSONPrimitive = str | int | float | bool | None
JSONValue = JSONPrimitive | dict[str, Any] | list[Any]

# JSONObject 和 JSONArray 类型定义
# 注意：这里使用 Any 是为了避免递归，但通过验证器确保运行时类型安全
JSONObject = dict[str, Any]
JSONArray = list[Any]


def validate_json_object(value: Any) -> JSONObject:
    """
    验证并规范化 JSON 对象

    这个函数在运行时确保值是可序列化的，同时保持类型检查时的类型安全。
    """
    if not isinstance(value, dict):
        return {}
    # 使用序列化工具确保所有值都是可序列化的
    return Serializer.serialize_dict(value)


def validate_json_value(value: Any) -> JSONValue:
    """
    验证并规范化 JSON 值

    这个函数在运行时确保值是可序列化的。
    """
    return Serializer.serialize(value)


# 使用 Annotated 类型增强类型信息，同时提供运行时验证
# 这样既保持了类型安全，又避免了递归问题
SerializableDict = Annotated[JSONObject, PlainValidator(validate_json_object)]
SerializableValue = Annotated[JSONValue, PlainValidator(validate_json_value)]


class SerializationError(Exception):
    """序列化错误"""

    pass


class Serializer:
    """
    统一序列化工具类

    提供递归序列化功能，确保所有对象都能被转换为 JSON 兼容格式。
    特别处理 LiteLLM 对象，避免 Pydantic 序列化警告。
    """

    @classmethod
    def serialize(cls, value: Any) -> JSONValue:
        """
        序列化值，确保所有对象都被转换为可序列化的格式

        Args:
            value: 要序列化的值

        Returns:
            JSON 兼容的值

        Raises:
            SerializationError: 如果无法序列化值
        """
        try:
            return cls._serialize_value(value)
        except Exception as e:
            logger.error("Serialization failed: %s", e)
            raise SerializationError(f"Failed to serialize value: {e}") from e

    @classmethod
    def serialize_dict(cls, value: dict[str, Any]) -> JSONObject:
        """
        序列化字典，确保所有值都是 JSON 兼容的

        Args:
            value: 要序列化的字典

        Returns:
            JSON 兼容的字典
        """
        if not isinstance(value, dict):
            return {}
        return cls.serialize(value)  # type: ignore[return-value]

    @classmethod
    def _serialize_value(cls, v: Any) -> JSONValue:
        """递归序列化值，确保所有对象都被转换为可序列化的格式"""
        # 基本类型直接返回
        if isinstance(v, str | int | float | bool | None):
            return v

        # Pydantic 模型转换为字典
        if isinstance(v, BaseModel):
            logger.debug("Serializing Pydantic model: %s", type(v).__name__)
            return v.model_dump(mode="json")

        # 字典和列表递归处理
        if isinstance(v, dict):
            return {k: cls._serialize_value(val) for k, val in v.items()}
        if isinstance(v, list):
            return [cls._serialize_value(item) for item in v]

        # 处理对象（LiteLLM 或其他）
        if hasattr(v, "__dict__") or hasattr(v, "__slots__"):
            result = cls._serialize_object(v)
            if result:
                return result

        # 最后尝试转换为字符串（避免存储不可序列化的对象）
        return str(v)

    @classmethod
    def _is_litellm_object(cls, v: Any) -> bool:
        """检查是否是 LiteLLM 对象"""
        type_name = type(v).__name__
        module_name = type(v).__module__ if hasattr(type(v), "__module__") else ""
        return "litellm" in module_name.lower() or any(
            name in type_name
            for name in [
                "Message",
                "Choices",
                "StreamingChoices",
                "Usage",
                "Function",
                "Tool",
                "Delta",
            ]
        )

    @classmethod
    def _serialize_object(cls, v: Any) -> dict[str, Any] | None:
        """序列化对象，尝试识别特定类型"""
        result: dict[str, Any] = {}
        type_name = type(v).__name__

        try:
            # 尝试识别并序列化特定类型的对象
            if cls._is_message_object(v):
                result = cls._serialize_message_object(v)
            elif cls._is_choices_object(v):
                result = cls._serialize_choices_object(v)
            elif cls._is_usage_object(v):
                result = cls._serialize_usage_object(v)
            elif cls._is_function_object(v):
                result = cls._serialize_function_object(v)
            elif cls._is_tool_object(v):
                result = cls._serialize_tool_object(v)

            # 如果没有识别为特定类型，尝试通用序列化
            if not result:
                result = cls._serialize_generic_object(v)

            return result if result else None
        except Exception as e:
            logger.debug("Error serializing object %s: %s", type_name, e)
            return None

    @classmethod
    def _is_message_object(cls, v: Any) -> bool:
        """检查是否是 Message 对象"""
        has_content_or_role = (
            hasattr(v, "content") or hasattr(v, "role") or hasattr(v, "tool_calls")
        )
        has_role_or_content = hasattr(v, "role") or (
            hasattr(v, "content") and not hasattr(v, "message")
        )
        return bool(has_content_or_role and has_role_or_content)

    @classmethod
    def _serialize_message_object(cls, v: Any) -> dict[str, Any]:
        """序列化 Message 对象"""
        result: dict[str, Any] = {}
        for attr in [
            "content",
            "role",
            "tool_calls",
            "tool_call_id",
            "name",
            "arguments",
            "function",
        ]:
            if hasattr(v, attr):
                attr_value = getattr(v, attr)
                if attr_value is not None or attr == "content":
                    result[attr] = cls._serialize_value(attr_value)
        return result

    @classmethod
    def _is_choices_object(cls, v: Any) -> bool:
        """检查是否是 Choices 对象"""
        return bool(
            hasattr(v, "message")
            or hasattr(v, "finish_reason")
            or hasattr(v, "index")
            or hasattr(v, "delta")
        )

    @classmethod
    def _serialize_choices_object(cls, v: Any) -> dict[str, Any]:
        """序列化 Choices 对象"""
        result: dict[str, Any] = {}
        for attr in ["message", "finish_reason", "index", "delta"]:
            if hasattr(v, attr):
                attr_value = getattr(v, attr)
                if attr_value is not None:
                    result[attr] = cls._serialize_value(attr_value)
        return result

    @classmethod
    def _is_usage_object(cls, v: Any) -> bool:
        """检查是否是 Usage 对象"""
        return bool(
            hasattr(v, "prompt_tokens")
            or hasattr(v, "completion_tokens")
            or hasattr(v, "total_tokens")
        )

    @classmethod
    def _serialize_usage_object(cls, v: Any) -> dict[str, Any]:
        """序列化 Usage 对象"""
        result: dict[str, Any] = {}
        for attr in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            if hasattr(v, attr):
                attr_value = getattr(v, attr)
                if attr_value is not None:
                    result[attr] = cls._serialize_value(attr_value)
        return result

    @classmethod
    def _is_function_object(cls, v: Any) -> bool:
        """检查是否是 Function 对象"""
        return bool(hasattr(v, "name") or hasattr(v, "arguments"))

    @classmethod
    def _serialize_function_object(cls, v: Any) -> dict[str, Any]:
        """序列化 Function 对象"""
        result: dict[str, Any] = {}
        for attr in ["name", "arguments"]:
            if hasattr(v, attr):
                attr_value = getattr(v, attr)
                if attr_value is not None:
                    result[attr] = cls._serialize_value(attr_value)
        return result

    @classmethod
    def _is_tool_object(cls, v: Any) -> bool:
        """检查是否是 Tool 对象"""
        return bool(hasattr(v, "id") or hasattr(v, "type") or hasattr(v, "function"))

    @classmethod
    def _serialize_tool_object(cls, v: Any) -> dict[str, Any]:
        """序列化 Tool 对象"""
        result: dict[str, Any] = {}
        for attr in ["id", "type", "function"]:
            if hasattr(v, attr):
                attr_value = getattr(v, attr)
                if attr_value is not None:
                    result[attr] = cls._serialize_value(attr_value)
        return result

    @classmethod
    def _serialize_generic_object(cls, v: Any) -> dict[str, Any]:
        """序列化通用对象（提取所有非私有属性）"""
        result: dict[str, Any] = {}
        attrs = getattr(v, "__dict__", {})
        for key, val in attrs.items():
            if not key.startswith("_"):
                result[key] = cls._serialize_value(val)
        return result
