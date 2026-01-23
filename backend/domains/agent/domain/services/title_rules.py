"""
Title Domain Rules - 标题领域规则

包含标题生成相关的业务规则和策略定义。
"""

from enum import Enum

# =============================================================================
# 默认标题配置（业务规则）
# =============================================================================
# 这些标题被视为默认标题，可以被自动生成的标题覆盖。
# 如果用户手动设置了其他标题，则不会被自动生成覆盖（保护用户设置）
# =============================================================================
DEFAULT_TITLES: frozenset[str] = frozenset(
    {
        "新对话",
        "新会话",
        "New Conversation",
        "New Chat",
        "",  # 空字符串也被视为默认标题
    }
)


def is_default_title(title: str | None) -> bool:
    """检查标题是否为默认标题

    业务规则：
    - None 被视为默认标题
    - 空字符串被视为默认标题
    - 预定义的默认标题（如"新对话"）被视为默认标题

    Args:
        title: 会话标题（可能为 None）

    Returns:
        如果是默认标题或 None，返回 True；否则返回 False
    """
    if title is None:
        return True
    return title in DEFAULT_TITLES


class TitleGenerationStrategy(str, Enum):
    """标题生成策略"""

    FIRST_MESSAGE = "first_message"  # 根据第一条消息生成
    SUMMARY = "summary"  # 根据多条消息总结生成
    MANUAL = "manual"  # 手动设置
