"""
API 参数解析 - 共享的查询/路径参数解析工具

供各 router 复用，避免重复的 422 校验逻辑。
"""

import uuid

from fastapi import HTTPException

__all__ = ["parse_optional_uuid"]


def parse_optional_uuid(
    value: str | None,
    param_name: str = "session_id",
) -> uuid.UUID | None:
    """将可选字符串解析为 UUID，解析失败时统一抛出 422。

    Args:
        value: 待解析字符串，None 或空则返回 None
        param_name: 参数名（用于错误详情）

    Returns:
        解析后的 UUID，或 None

    Raises:
        HTTPException: 422，当 value 非空且无法解析为 UUID 时
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=422, detail=f"Invalid {param_name}") from None
