"""用户创建后的默认租户编排（单点、可观测）。"""

from __future__ import annotations

from logging import Logger
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from libs.iam.tenancy import DefaultTenantProvisionerPort
from utils.logging import get_logger

logger = get_logger(__name__)


async def provision_default_tenant_for_new_user(
    *,
    session: AsyncSession,
    provisioner: DefaultTenantProvisionerPort,
    user_id: uuid.UUID,
    display_name: str | None,
    log: Logger | None = None,
) -> bool:
    """确保默认可归属租户存在。

    产品策略：失败不阻断用户创建，但必须留下可观测日志便于补偿/告警。

    Returns:
        True 若供给成功，False 若发生异常（已记录 warning）。
    """
    log = log or logger
    try:
        await provisioner.ensure_default_tenant(
            session,
            user_id,
            display_name=display_name,
        )
        return True
    except Exception as exc:  # pragma: no cover - 依赖 DB/网关实现
        log.warning(
            "Default tenant provisioning failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return False


__all__ = ["provision_default_tenant_for_new_user"]
