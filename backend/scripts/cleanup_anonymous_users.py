"""
清理遗留的匿名 shadow User 记录（一次性 / 维护脚本）

当前架构中匿名用户不再写入 ``users`` 表：
- Cookie → 内存 ``Principal``
- 业务数据 ``tenant_id`` = ``resolve_anonymous_tenant_id(cookie_id)``（UUID v5）

本脚本用于删除迁移前遗留的 ``role=anonymous`` shadow 用户及其 personal team。
若已执行 Alembic ``20260606_anon_tenant``，通常无需再运行。

使用方法:
    uv run python scripts/cleanup_anonymous_users.py --dry-run
    uv run python scripts/cleanup_anonymous_users.py
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # pylint: disable=wrong-import-position
from sqlalchemy.ext.asyncio import (  # pylint: disable=wrong-import-position
    AsyncSession,
    create_async_engine,
)

from bootstrap.config_loader import get_app_config  # pylint: disable=wrong-import-position
from domains.identity.domain.anonymous_tenant import (
    resolve_anonymous_tenant_id,  # pylint: disable=wrong-import-position
)
from domains.identity.domain.orphan_tenant_tables import (
    TENANT_SCOPED_TABLES_FOR_MIGRATION,  # pylint: disable=wrong-import-position
)


async def get_engine():
    config = get_app_config()
    return create_async_engine(config.infra.database_url, echo=False)


async def list_shadow_users(session: AsyncSession) -> list[tuple]:
    result = await session.execute(
        text(
            """
            SELECT u.id, u.email, u.created_at,
                   u.settings->>'anonymous_cookie_id' AS cookie_id,
                   t.id AS team_id
            FROM users u
            LEFT JOIN gateway_teams t
                ON t.owner_user_id = u.id AND t.kind = 'personal' AND t.is_active = TRUE
            WHERE u.role = 'anonymous'
            ORDER BY u.created_at DESC
            """
        )
    )
    return result.fetchall()


async def migrate_and_delete_shadow(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    team_id: uuid.UUID | None,
    cookie_id: str,
) -> None:
    new_tenant = resolve_anonymous_tenant_id(cookie_id)
    if team_id is not None and team_id != new_tenant:
        for table in TENANT_SCOPED_TABLES_FOR_MIGRATION:
            await session.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET tenant_id = :new_tenant
                    WHERE tenant_id = :old_tenant
                    """
                ),
                {"new_tenant": new_tenant, "old_tenant": team_id},
            )
        await session.execute(
            text("DELETE FROM gateway_team_members WHERE team_id = :team_id"),
            {"team_id": team_id},
        )
        await session.execute(
            text("DELETE FROM gateway_teams WHERE id = :team_id"),
            {"team_id": team_id},
        )
    await session.execute(
        text("DELETE FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )


async def cleanup_shadow_users(*, dry_run: bool = True) -> None:
    engine = await get_engine()
    async with AsyncSession(engine) as session:
        rows = await list_shadow_users(session)
        if not rows:
            print("没有找到 shadow 匿名用户，无需清理。")
            await engine.dispose()
            return

        print(f"找到 {len(rows)} 个 shadow 匿名用户")
        for user_id, email, created_at, cookie_id, team_id in rows:
            print(f"  - {email} | user={user_id} | team={team_id} | cookie={cookie_id}")

        if dry_run:
            print("\n[预览模式] 未执行删除")
            await engine.dispose()
            return

        for user_id, _email, _created_at, cookie_id, team_id in rows:
            if not cookie_id:
                print(f"跳过无 cookie_id 的用户 {user_id}")
                continue
            await migrate_and_delete_shadow(
                session,
                user_id=uuid.UUID(str(user_id)),
                team_id=uuid.UUID(str(team_id)) if team_id else None,
                cookie_id=str(cookie_id),
            )

        await session.commit()
        print(f"\n已迁移并删除 {len(rows)} 个 shadow 匿名用户")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="清理遗留 shadow 匿名用户")
    parser.add_argument("--dry-run", action="store_true", help="预览，不执行删除")
    args = parser.parse_args()
    asyncio.run(cleanup_shadow_users(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
