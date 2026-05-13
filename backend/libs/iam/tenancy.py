"""租户 / 作用域类型与端口（与持久化表名 team 解耦）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType, Protocol
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

TenantId = NewType("TenantId", uuid.UUID)


@dataclass(frozen=True)
class ScopeContext:
    """当前请求在租户作用域下的解析结果（逻辑模型）。"""

    tenant_id: TenantId
    subject_user_id: uuid.UUID
    member_role: str | None


class DefaultTenantProvisionerPort(Protocol):
    """用户创建后确保存在默认可归属租户（如 personal team）。"""

    async def ensure_default_tenant(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        display_name: str | None,
    ) -> TenantId:
        """幂等；失败应抛异常由编排层记录。"""


class MembershipPort(Protocol):
    """租户内成员角色（权威数据可在 tenancy / gateway 实现）。"""

    async def member_role(
        self,
        session: AsyncSession,
        *,
        tenant_id: TenantId,
        user_id: uuid.UUID,
    ) -> str | None:
        """非成员返回 None。"""


__all__ = [
    "DefaultTenantProvisionerPort",
    "MembershipPort",
    "ScopeContext",
    "TenantId",
]
