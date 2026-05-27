"""匿名 orphan tenant 数据清理（无 shadow User）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.domain.orphan_tenant_tables import ORPHAN_TENANT_CLEANUP_TABLES

# 子表优先删除；sessions 删除会级联 messages。
_ORPHAN_DELETE_ORDER: tuple[str, ...] = tuple(reversed(ORPHAN_TENANT_CLEANUP_TABLES))


async def cleanup_orphan_anonymous_tenants(
    session: AsyncSession,
    *,
    retention_days: int = 90,
) -> int:
    """删除 orphan tenant 行（开发环境匿名数据为主）。

    判定：``tenant_id NOT IN gateway_teams`` 且 ``updated_at < cutoff``。
    注册用户 personal team 正常情况下总在 ``gateway_teams`` 中；若 team 被误删
    而业务行仍在，也会被本启发式清理——**仅建议在 dev / 维护脚本中使用**。

    Returns:
        删除的行数合计（各表 rowcount 之和）。
    """
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    total = 0
    for table in _ORPHAN_DELETE_ORDER:
        result = await session.execute(
            text(
                f"""
                DELETE FROM {table} x
                WHERE x.tenant_id IS NOT NULL
                  AND x.tenant_id NOT IN (SELECT id FROM gateway_teams)
                  AND x.updated_at < :cutoff
                """
            ),
            {"cutoff": cutoff},
        )
        total += result.rowcount or 0
    if total:
        await session.flush()
    return total


async def cleanup_anonymous_users(session: AsyncSession, *, retention_days: int = 90) -> int:
    """兼容旧入口名：清理 orphan anonymous tenant 数据。"""
    return await cleanup_orphan_anonymous_tenants(session, retention_days=retention_days)


__all__ = ["cleanup_anonymous_users", "cleanup_orphan_anonymous_tenants"]
