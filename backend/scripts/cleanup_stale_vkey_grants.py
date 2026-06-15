"""
清理过期 vkey 跨团队授权行（运维补救脚本，非生产必需）

**正常路径（事件驱动，不依赖 cron）**：
- 用户被移出 team / 主动退出 → ``team_service.remove_member`` 同步调用
  ``revoke_grants_for_user_team_membership``
- 团队被删除 → ``team_service.delete_shared_team`` 同步撤销指向该 team 的全部 grant

本脚本仅用于：历史脏数据修复、绕过应用层直接改库后的对账、一次性手工巡检。
日常发版**无需**注册定时任务。

使用方法:
    uv run python scripts/cleanup_stale_vkey_grants.py --dry-run   # 预览
    uv run python scripts/cleanup_stale_vkey_grants.py             # 执行
"""

import argparse
import asyncio
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update  # pylint: disable=wrong-import-position

from domains.gateway.infrastructure.models.virtual_key_team_grant import (  # pylint: disable=wrong-import-position
    GatewayVirtualKeyTeamGrant,
)
from domains.tenancy.infrastructure.models.team import (
    TeamMember,  # pylint: disable=wrong-import-position
)
from libs.db.database import get_session_context, init_db  # pylint: disable=wrong-import-position


async def run_cleanup(dry_run: bool = False) -> None:
    """扫描并撤销 membership 已失效的非自洽 grant 行。"""
    await init_db()

    async with get_session_context() as db:
        # ── 1. 查出所有需要检查的 active 非自洽 grant ──────────────────
        stmt = select(
            GatewayVirtualKeyTeamGrant.id,
            GatewayVirtualKeyTeamGrant.granted_by_user_id,
            GatewayVirtualKeyTeamGrant.tenant_id,
        ).where(
            GatewayVirtualKeyTeamGrant.is_active.is_(True),
            GatewayVirtualKeyTeamGrant.is_self.is_(False),
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            print("无需清理：没有非自洽 active grant 行")
            return

        # ── 2. 逐行检查 membership 是否仍存在 ────────────────────────
        stale_ids: list = []
        for row in rows:
            membership_exists = (
                select(TeamMember)
                .where(
                    TeamMember.user_id == row.granted_by_user_id,
                    TeamMember.team_id == row.tenant_id,
                )
                .exists()
            )
            still_member = (
                await db.execute(select(membership_exists))
            ).scalar()
            if not still_member:
                stale_ids.append(row.id)

        if not stale_ids:
            print(f"已检查 {len(rows)} 行，全部有效，无需清理")
            return

        if dry_run:
            print(f"[预览] 将撤销 {len(stale_ids)} 行过期 grant（共检查 {len(rows)} 行）")
            return

        # ── 3. 批量撤销 ─────────────────────────────────────────────
        from datetime import UTC
        from datetime import datetime as dt

        result = await db.execute(
            update(GatewayVirtualKeyTeamGrant)
            .where(GatewayVirtualKeyTeamGrant.id.in_(stale_ids))
            .values(
                is_active=False,
                revoked_at=dt.now(UTC),
                revoked_reason="membership_lost",
            )
        )
        await db.commit()
        print(f"已撤销 {result.rowcount} 行过期 grant（共检查 {len(rows)} 行）")


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 membership 失效的 vkey 跨团队授权")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不执行撤销",
    )
    args = parser.parse_args()
    asyncio.run(run_cleanup(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
