"""
Session Domain Entity and Services - 会话领域实体和服务

包含会话相关的业务规则和领域逻辑。
"""

from dataclasses import dataclass
from typing import Protocol
import uuid


class SessionLike(Protocol):
    """会话协议（用于类型检查）"""

    tenant_id: uuid.UUID


@dataclass(frozen=True)
class SessionOwner:
    """会话所有者值对象（已认证注册用户）。"""

    user_id: uuid.UUID

    @classmethod
    def from_user_id(cls, user_id: str) -> "SessionOwner":
        """从用户 ID 创建。"""
        return cls(user_id=uuid.UUID(user_id))

    @classmethod
    def from_principal_id(cls, principal_id: str) -> "SessionOwner":
        """从 Principal ID 创建。"""
        return cls(user_id=uuid.UUID(principal_id))


class SessionDomainService:
    """会话领域服务

    包含跨实体的会话业务逻辑。
    """

    @staticmethod
    def check_tenant_ownership(session: SessionLike, expected_tenant_id: uuid.UUID) -> bool:
        """检查会话是否落在预期 tenant（personal / shared team）。"""
        return session.tenant_id == expected_tenant_id

    @staticmethod
    def validate_session_creation(user_id: uuid.UUID) -> SessionOwner:
        """验证会话创建参数并返回所有者值对象。"""
        return SessionOwner(user_id=user_id)
