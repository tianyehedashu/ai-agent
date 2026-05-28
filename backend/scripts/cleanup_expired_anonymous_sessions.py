"""
清理过期的匿名 orphan tenant 数据（开发环境维护脚本）

匿名会话的 ``tenant_id`` 不在 ``gateway_teams`` 中；按 ``updated_at`` 清理超 retention 的行。
启发式 ``tenant_id NOT IN gateway_teams`` 也会匹配 team 被误删的脏数据——**仅建议在 dev 使用**。
``sessions`` 删除会级联 ``messages``。

使用方法:
    uv run python scripts/cleanup_expired_anonymous_sessions.py --dry-run
    uv run python scripts/cleanup_expired_anonymous_sessions.py --days 30
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # pylint: disable=wrong-import-position
from sqlalchemy.ext.asyncio import (  # pylint: disable=wrong-import-position
    AsyncSession,
    create_async_engine,
)

from bootstrap.config_loader import get_app_config  # pylint: disable=wrong-import-position
from domains.identity.domain.orphan_tenant_tables import (
    ORPHAN_TENANT_CLEANUP_TABLES,  # pylint: disable=wrong-import-position
)


async def get_engine():
    config = get_app_config()
    return create_async_engine(config.infra.database_url, echo=False)


async def count_orphan_sessions(session: AsyncSession, cutoff: datetime) -> list[tuple]:
    result = await session.execute(
        text(
            """
            SELECT s.id, s.title, s.tenant_id, s.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count
            FROM sessions s
            WHERE s.tenant_id NOT IN (SELECT id FROM gateway_teams)
              AND s.updated_at < :cutoff
            ORDER BY s.updated_at ASC
            """
        ),
        {"cutoff": cutoff},
    )
    return result.fetchall()


async def delete_orphan_tenant_rows(session: AsyncSession, cutoff: datetime) -> int:
    total = 0
    for table in reversed(ORPHAN_TENANT_CLEANUP_TABLES):
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
    return total


async def cleanup_expired_sessions(*, days: int = 30, dry_run: bool = True) -> None:
    engine = await get_engine()
    cutoff = datetime.now(UTC) - timedelta(days=days)

    async with AsyncSession(engine) as session:
        expired = await count_orphan_sessions(session, cutoff)
        if not expired:
            print(f"没有找到 {days} 天前的 orphan 匿名 Session。")
            await engine.dispose()
            return

        total_messages = sum(int(row[4]) for row in expired)
        print(f"\n找到 {len(expired)} 个过期 orphan Session，关联消息 {total_messages} 条")
        print(f"截止日期: {cutoff.isoformat()} ({days} 天前)")

        for i, row in enumerate(expired[:10]):
            sid, title, tenant_id, updated_at, msg_count = row
            print(
                f"  {i + 1}. {(title or '(无标题)')[:30]:<30} | "
                f"tenant={str(tenant_id)[:8]}… | msgs={msg_count} | {updated_at}"
            )
        if len(expired) > 10:
            print(f"  ... 还有 {len(expired) - 10} 个")

        if dry_run:
            print("\n[预览模式] 未执行删除")
            await engine.dispose()
            return

        deleted = await delete_orphan_tenant_rows(session, cutoff)
        await session.commit()
        print(f"\n清理完成，共删除 {deleted} 行（含级联）")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="清理过期 orphan 匿名 tenant 数据")
    parser.add_argument("--days", "-d", type=int, default=30, help="retention 天数（默认 30）")
    parser.add_argument("--dry-run", action="store_true", help="预览，不执行删除")
    args = parser.parse_args()
    asyncio.run(cleanup_expired_sessions(days=args.days, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
