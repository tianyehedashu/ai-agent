"""
Identity Domain Types - 身份域类型定义

包含身份认证相关的核心类型：
- Principal: 身份主体（支持注册用户和匿名用户）
- 匿名用户常量
"""

from __future__ import annotations

from dataclasses import dataclass

# ============================================================================
# 匿名用户常量
# ============================================================================

ANONYMOUS_ID_PREFIX = "anonymous-"
"""匿名用户 ID 前缀，格式：anonymous-{uuid}"""

ANONYMOUS_EMAIL_SUFFIX = "@local"
"""匿名用户邮箱后缀"""


# ============================================================================
# Principal（身份主体）
# ============================================================================


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated or anonymous principal.

    统一的身份主体，支持注册用户和匿名用户。
    匿名用户 ID 格式：`anonymous-{uuid}`
    """

    id: str
    email: str
    name: str
    is_anonymous: bool = False

    @staticmethod
    def is_anonymous_id(user_id: str) -> bool:
        """检查是否为匿名用户 ID"""
        return user_id.startswith(ANONYMOUS_ID_PREFIX)

    @staticmethod
    def extract_anonymous_id(user_id: str) -> str:
        """从 Principal ID 中提取原始匿名用户 ID

        Args:
            user_id: Principal ID（格式：anonymous-{uuid} 或普通 UUID）

        Returns:
            如果是匿名用户格式，返回 uuid 部分；否则返回原 ID
        """
        if user_id.startswith(ANONYMOUS_ID_PREFIX):
            return user_id[len(ANONYMOUS_ID_PREFIX) :]
        return user_id

    @staticmethod
    def make_anonymous_id(anonymous_user_id: str) -> str:
        """创建匿名用户 Principal ID"""
        return f"{ANONYMOUS_ID_PREFIX}{anonymous_user_id}"

    @staticmethod
    def make_anonymous_email(anonymous_user_id: str) -> str:
        """创建匿名用户的邮箱"""
        return f"{ANONYMOUS_ID_PREFIX}{anonymous_user_id}{ANONYMOUS_EMAIL_SUFFIX}"

    def get_anonymous_user_id(self) -> str | None:
        """获取原始匿名用户 ID（用于数据库查询）"""
        if self.is_anonymous:
            return self.extract_anonymous_id(self.id)
        return None

    def get_user_id(self) -> str | None:
        """获取注册用户 ID（用于数据库查询）"""
        if not self.is_anonymous:
            return self.id
        return None
