"""
API 参数解析 - 共享的查询/路径参数解析工具

供各 router 复用，避免重复的 422 校验逻辑。
"""

import uuid

from libs.exceptions import ValidationError

__all__ = ["coerce_optional_uuid", "parse_optional_uuid"]


def coerce_optional_uuid(value: object) -> uuid.UUID | None:
    """Pydantic ``mode='before'``：JSON 字符串 UUID → ``uuid.UUID``（兼容 strict 模型）。"""
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value.strip())
        except ValueError as exc:
            raise ValueError("must be a valid UUID") from exc
    raise ValueError("must be a UUID string")


def parse_optional_uuid(
    value: str | None,
    param_name: str = "session_id",
) -> uuid.UUID | None:
    """将可选字符串解析为 UUID，解析失败时统一抛出 ValidationError。

    Args:
        value: 待解析字符串，None 或空则返回 None
        param_name: 参数名（用于错误详情）

    Returns:
        解析后的 UUID，或 None

    Raises:
        ValidationError: 当 value 非空且无法解析为 UUID 时
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(f"Invalid {param_name}") from None
