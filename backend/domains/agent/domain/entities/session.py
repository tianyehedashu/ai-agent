"""
Session Domain Entity and Services - 会话领域实体和服务

包含会话相关的业务规则和领域逻辑。
"""

from dataclasses import dataclass
from typing import Protocol
import uuid


class SessionLike(Protocol):
    """会话协议（用于类型检查）"""

    user_id: uuid.UUID | None
    anonymous_user_id: str | None


@dataclass(frozen=True)
class SessionOwner:
    """会话所有者值对象

    封装会话所有者的身份信息，支持注册用户和匿名用户。
    使用值对象确保不可变性和类型安全。
    """

    user_id: uuid.UUID | None = None
    anonymous_user_id: str | None = None

    def __post_init__(self) -> None:
        """验证业务规则：必须有且仅有一个用户标识"""
        if not self.user_id and not self.anonymous_user_id:
            raise ValueError("Either user_id or anonymous_user_id must be provided")
        if self.user_id and self.anonymous_user_id:
            raise ValueError("Cannot provide both user_id and anonymous_user_id")

    @property
    def is_anonymous(self) -> bool:
        """是否为匿名用户"""
        return self.anonymous_user_id is not None

    @classmethod
    def from_user_id(cls, user_id: str) -> "SessionOwner":
        """从用户 ID 创建（注册用户）"""
        return cls(user_id=uuid.UUID(user_id))

    @classmethod
    def from_anonymous_id(cls, anonymous_id: str) -> "SessionOwner":
        """从匿名 ID 创建（匿名用户）"""
        return cls(anonymous_user_id=anonymous_id)

    @classmethod
    def from_principal_id(cls, principal_id: str, is_anonymous: bool) -> "SessionOwner":
        """从 Principal ID 创建

        Args:
            principal_id: Principal 的 ID（可能包含 'anonymous-' 前缀）
            is_anonymous: 是否为匿名用户

        Returns:
            SessionOwner 实例
        """
        if is_anonymous:
            # 提取匿名用户的真实 ID（去除 'anonymous-' 前缀）
            from domains.identity.domain.types import (
                Principal,  # pylint: disable=import-outside-toplevel
            )

            return cls(anonymous_user_id=Principal.extract_anonymous_id(principal_id))
        return cls(user_id=uuid.UUID(principal_id))


class SessionDomainService:
    """会话领域服务

    包含跨实体的会话业务逻辑。
    """

    @staticmethod
    def check_ownership(session: SessionLike, owner: SessionOwner) -> bool:
        """检查会话所有权

        业务规则：
        - 匿名用户：session.anonymous_user_id 必须匹配
        - 注册用户：session.user_id 必须匹配

        Args:
            session: 会话实体
            owner: 预期的所有者

        Returns:
            是否拥有所有权
        """
        if owner.is_anonymous:
            return session.anonymous_user_id == owner.anonymous_user_id
        return session.user_id == owner.user_id

    @staticmethod
    def validate_session_creation(
        user_id: uuid.UUID | None,
        anonymous_user_id: str | None,
    ) -> SessionOwner:
        """验证会话创建参数

        业务规则：必须有且仅有一个用户标识。

        Args:
            user_id: 注册用户 ID
            anonymous_user_id: 匿名用户 ID

        Returns:
            SessionOwner 值对象

        Raises:
            ValueError: 如果参数不符合业务规则时
        """
        return SessionOwner(user_id=user_id, anonymous_user_id=anonymous_user_id)
