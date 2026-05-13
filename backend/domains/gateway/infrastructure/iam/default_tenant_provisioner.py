"""DefaultTenantProvisionerPort 的 gateway 实现（personal team）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.application.team_service import TeamService
from libs.iam.tenancy import TenantId


class GatewayDefaultTenantProvisioner:
    """将默认可归属租户映射为现有 Team 表（personal）。"""

    async def ensure_default_tenant(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        display_name: str | None,
    ) -> TenantId:
        team = await TeamService(session).ensure_personal_team(
            user_id,
            display_name=display_name,
        )
        return TenantId(team.id)


__all__ = ["GatewayDefaultTenantProvisioner"]
