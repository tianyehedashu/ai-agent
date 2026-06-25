"""
清理悬空路由跨团队共享授权行（运维补救脚本，非生产必需）

**正常路径（事件驱动，不依赖 cron）**：
- 用户被移出 team / 主动退出 → ``team_service.remove_member`` 同步调用
  ``revoke_route_grants_for_user_team_membership``
- 团队被删除 → ``team_service.delete_shared_team`` 同步撤销指向该 team 的全部 grant
- 路由被删除 → ``delete_gateway_route`` 级联软撤销其全部 grant

本脚本仅用于：历史脏数据修复、绕过应用层直接改库后的对账、一次性手工巡检。
扫描并撤销以下悬空行：
1. granted_by_user_id 已不再是 tenant_id 的成员（membership 失效）
2. route_id 对应路由已删除
3. tenant_id 对应团队已删除/停用

使用方法:
    uv run python scripts/cleanup_stale_route_grants.py --dry-run   # 预览
    uv run python scripts/cleanup_stale_route_grants.py             # 执行
"""

import argparse
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import UTC  # pylint: disable=wrong-import-position
from datetime import datetime as dt

from sqlalchemy import select, update  # pylint: disable=wrong-import-position

from domains.gateway.infrastructure.models.gateway_route import (  # pylint: disable=wrong-import-position
    GatewayRoute,
)
from domains.gateway.infrastructure.models.gateway_route_team_grant import (  # pylint: disable=wrong-import-position
    GatewayRouteTeamGrant,
)
from domains.tenancy.infrastructure.models.team import (  # pylint: disable=wrong-import-position
    Team,
    TeamMember,
)
from libs.db.database import (  # pylint: disable=wrong-import-position
    get_session_context,
    init_db,
)


async def run_cleanup(dry_run: bool = False) -> None:
    await init_db()

    async with get_session_context() as db:
        stmt = select(
            GatewayRouteTeamGrant.id,
            GatewayRouteTeamGrant.route_id,
            GatewayRouteTeamGrant.granted_by_user_id,
            GatewayRouteTeamGrant.tenant_id,
        ).where(GatewayRouteTeamGrant.is_active.is_(True))
        rows = (await db.execute(stmt)).all()
        if not rows:
            print("无需清理：没有 active 路由共享授权行")
            return

        stale: dict[object, str] = {}
        for row in rows:
            route_exists = (
                await db.execute(
                    select(select(GatewayRoute).where(GatewayRoute.id == row.route_id).exists())
                )
            ).scalar()
            if not route_exists:
                stale[row.id] = "route_deleted"
                continue
            team_active = (
                await db.execute(
                    select(
                        select(Team)
                        .where(Team.id == row.tenant_id, Team.is_active.is_(True))
                        .exists()
                    )
                )
            ).scalar()
            if not team_active:
                stale[row.id] = "team_archived"
                continue
            still_member = (
                await db.execute(
                    select(
                        select(TeamMember)
                        .where(
                            TeamMember.user_id == row.granted_by_user_id,
                            TeamMember.team_id == row.tenant_id,
                        )
                        .exists()
                    )
                )
            ).scalar()
            if not still_member:
                stale[row.id] = "membership_lost"

        if not stale:
            print(f"已检查 {len(rows)} 行，全部有效，无需清理")
            return

        if dry_run:
            print(f"[预览] 将撤销 {len(stale)} 行悬空 grant（共检查 {len(rows)} 行）")
            for gid, reason in stale.items():
                print(f"  - {gid}: {reason}")
            return

        # 按 reason 分组批量撤销，保留各自语义
        by_reason: dict[str, list[object]] = {}
        for gid, reason in stale.items():
            by_reason.setdefault(reason, []).append(gid)
        total = 0
        for reason, ids in by_reason.items():
            result = await db.execute(
                update(GatewayRouteTeamGrant)
                .where(GatewayRouteTeamGrant.id.in_(ids))
                .values(is_active=False, revoked_at=dt.now(UTC), revoked_reason=reason)
            )
            total += result.rowcount or 0
        await db.commit()
        print(f"已撤销 {total} 行悬空 grant（共检查 {len(rows)} 行）")


def main() -> None:
    parser = argparse.ArgumentParser(description="清理悬空路由跨团队共享授权")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行撤销")
    args = parser.parse_args()
    asyncio.run(run_cleanup(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
