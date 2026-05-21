"""DefaultTenantProvisionerPort 的 tenancy 实现（personal team 权威）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner
from libs.iam.tenancy import TenantId


class TenancyDefaultTenantProvisioner:
    """将默认可归属租户映射为 personal team（幂等）。"""

    async def ensure_default_tenant(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        display_name: str | None,
    ) -> TenantId:
        tid = await PersonalTeamProvisioner(session).ensure_personal_team(
            user_id,
            display_name=display_name,
        )
        return TenantId(tid)


__all__ = ["TenancyDefaultTenantProvisioner"]
