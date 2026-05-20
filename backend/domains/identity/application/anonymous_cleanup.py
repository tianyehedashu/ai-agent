"""匿名用户清理后台任务入口（供 scheduler / admin 调用）。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.anonymous_user_provisioner import AnonymousUserProvisioner


async def cleanup_anonymous_users(session: AsyncSession, *, retention_days: int = 90) -> int:
    return await AnonymousUserProvisioner(session).cleanup_anonymous_users(retention_days)


__all__ = ["cleanup_anonymous_users"]
