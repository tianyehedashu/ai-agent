"""Shared kernel types."""

from dataclasses import dataclass

# =============================================================================
# 匿名用户常量
# =============================================================================

ANONYMOUS_ID_PREFIX = "anonymous-"
"""匿名用户 ID 前缀，格式：anonymous-{uuid}"""

ANONYMOUS_EMAIL_SUFFIX = "@local"
"""匿名用户邮箱后缀"""


# =============================================================================
# Principal（身份主体）
# =============================================================================


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated or anonymous principal.

    统一的身份主体，支持注册用户和匿名用户    匿名用户ID 格式`anonymous-{uuid}`?    """

    id: str
    email: str
    name: str
    is_anonymous: bool = False

    @staticmethod
    def is_anonymous_id(user_id: str) -> bool:
        """检查是否为匿名用户 ID

        Args:
            user_id: 用户 ID

        Returns:
            如果是匿名用ID 格式则返True
        """
        return user_id.startswith(ANONYMOUS_ID_PREFIX)

    @staticmethod
    def extract_anonymous_id(user_id: str) -> str:
        """?Principal ID 中提取原始匿名用ID

        Args:
            user_id: Principal ID（格式：anonymous-{uuid} 或普UUID?
        Returns:
            如果是匿名用户格式，返回 uuid 部分；否则返回原ID
        """
        if user_id.startswith(ANONYMOUS_ID_PREFIX):
            return user_id[len(ANONYMOUS_ID_PREFIX) :]
        return user_id

    @staticmethod
    def make_anonymous_id(anonymous_user_id: str) -> str:
        """创建匿名用户Principal ID

        Args:
            anonymous_user_id: 原始匿名用户 ID（UUID 格式
        Returns:
            格式化的 Principal ID：anonymous-{uuid}
        """
        return f"{ANONYMOUS_ID_PREFIX}{anonymous_user_id}"

    @staticmethod
    def make_anonymous_email(anonymous_user_id: str) -> str:
        """创建匿名用户的邮
        Args:
            anonymous_user_id: 原始匿名用户 ID（UUID 格式
        Returns:
            格式化的邮箱：anonymous-{uuid}@local
        """
        return f"{ANONYMOUS_ID_PREFIX}{anonymous_user_id}{ANONYMOUS_EMAIL_SUFFIX}"

    def get_anonymous_user_id(self) -> str | None:
        """获取原始匿名用户 ID（用于数据库查询
        Returns:
            如果是匿名用户，返回原始 UUID；否则返None
        """
        if self.is_anonymous:
            return self.extract_anonymous_id(self.id)
        return None

    def get_user_id(self) -> str | None:
        """获取注册用户 ID（用于数据库查询
        Returns:
            如果是注册用户，返回用户 ID；否则返None
        """
        if not self.is_anonymous:
            return self.id
        return None
