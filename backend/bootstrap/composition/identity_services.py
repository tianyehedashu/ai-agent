"""Identity 域 FastAPI 依赖工厂。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application import UserUseCase
from libs.db.database import get_db
from libs.iam.deps import get_default_tenant_provisioner
from libs.iam.tenancy import DefaultTenantProvisionerPort

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_user_use_case(
    db: DbSession,
    tenant_provisioner: Annotated[
        DefaultTenantProvisionerPort, Depends(get_default_tenant_provisioner)
    ],
) -> UserUseCase:
    return UserUseCase(db, tenant_provisioner=tenant_provisioner)


__all__ = ["get_user_use_case"]
