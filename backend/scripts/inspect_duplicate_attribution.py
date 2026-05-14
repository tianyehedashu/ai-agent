"""排查桥接报 ``Multiple rows were found`` 的来源。

bridge fallback 信息：
    Gateway bridge call failed, fallback to direct LiteLLM:
    Multiple rows were found when one or none was required

历史来源（现已分别由 schema + 查询加固）：
1. ``TeamRepository.get_personal``：同一用户多条活跃 personal（迁移
   ``20260514_upt`` 部分唯一索引 + ``ORDER BY ... LIMIT 1``）；
2. ``VirtualKeyRepository.get_or_create_system_key``：同一 team 多条活跃 system
   vkey（迁移 ``20260513_uvk`` + ``ON CONFLICT DO NOTHING``）。

本脚本逐一报告重复行，便于定位哪一份并发写入留下的脏数据。

Usage:
    uv run python scripts/inspect_duplicate_attribution.py
    uv run python scripts/inspect_duplicate_attribution.py --user <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select, update  # pylint: disable=wrong-import-position

from domains.gateway.infrastructure.models.virtual_key import (  # pylint: disable=wrong-import-position
    GatewayVirtualKey,
)
from domains.tenancy.infrastructure.models.team import Team  # pylint: disable=wrong-import-position
from libs.db.database import (  # pylint: disable=wrong-import-position
    get_session_context,
    init_db,
)


async def _dup_personal_teams(session, user_filter: uuid.UUID | None) -> None:
    print("\n[1/2] Duplicate personal Team rows (owner_user_id + kind='personal' + is_active=True)")
    stmt = (
        select(
            Team.owner_user_id,
            func.count().label("n"),
        )
        .where(Team.kind == "personal", Team.is_active.is_(True))
        .group_by(Team.owner_user_id)
        .having(func.count() > 1)
    )
    if user_filter is not None:
        stmt = stmt.where(Team.owner_user_id == user_filter)
    rows = (await session.execute(stmt)).all()
    if not rows:
        print("  (no duplicates)")
        return
    for owner, n in rows:
        print(f"  owner={owner}  n={n}")
        detail = (
            await session.execute(
                select(Team)
                .where(
                    Team.owner_user_id == owner,
                    Team.kind == "personal",
                    Team.is_active.is_(True),
                )
                .order_by(Team.created_at)
            )
        ).scalars().all()
        for t in detail:
            print(
                f"    - id={t.id}  slug={t.slug}  created_at={t.created_at}  name={t.name}"
            )


async def _dup_system_vkeys(
    session, team_filter: uuid.UUID | None, *, do_fix: bool
) -> None:
    print(
        "\n[2/2] Duplicate system GatewayVirtualKey rows "
        "(team_id + is_system=True + is_active=True)"
    )
    stmt = (
        select(
            GatewayVirtualKey.team_id,
            func.count().label("n"),
        )
        .where(
            GatewayVirtualKey.is_system.is_(True),
            GatewayVirtualKey.is_active.is_(True),
        )
        .group_by(GatewayVirtualKey.team_id)
        .having(func.count() > 1)
    )
    if team_filter is not None:
        stmt = stmt.where(GatewayVirtualKey.team_id == team_filter)
    rows = (await session.execute(stmt)).all()
    if not rows:
        print("  (no duplicates)")
        return
    fixed_total = 0
    for team_id, n in rows:
        print(f"  team={team_id}  n={n}")
        detail = (
            await session.execute(
                select(GatewayVirtualKey)
                .where(
                    GatewayVirtualKey.team_id == team_id,
                    GatewayVirtualKey.is_system.is_(True),
                    GatewayVirtualKey.is_active.is_(True),
                )
                .order_by(GatewayVirtualKey.created_at)
            )
        ).scalars().all()
        dup_ids: list[uuid.UUID] = []
        for idx, k in enumerate(detail):
            tag = "KEEP" if idx == 0 else ("FIX " if do_fix else "DUP ")
            print(
                f"    - [{tag}] id={k.id}  key_id={k.key_id}  "
                f"created_at={k.created_at}  name={k.name}"
            )
            if idx > 0:
                dup_ids.append(k.id)
        if do_fix and dup_ids:
            await session.execute(
                update(GatewayVirtualKey)
                .where(GatewayVirtualKey.id.in_(dup_ids))
                .values(is_active=False)
            )
            fixed_total += len(dup_ids)
    if do_fix and fixed_total:
        await session.commit()
        print(f"\n  fixed {fixed_total} duplicate row(s) -> is_active=False")


async def run(args: argparse.Namespace) -> None:
    await init_db()
    user_filter = uuid.UUID(args.user) if args.user else None
    team_filter = uuid.UUID(args.team) if args.team else None
    async with get_session_context() as session:
        await _dup_personal_teams(session, user_filter)
        await _dup_system_vkeys(session, team_filter, do_fix=args.fix)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect (and optionally fix) duplicate attribution rows breaking GatewayBridge"
    )
    parser.add_argument("--user", type=str, default=None)
    parser.add_argument("--team", type=str, default=None)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="保留最早创建的一条 system vkey，把其它副本置 is_active=False",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
