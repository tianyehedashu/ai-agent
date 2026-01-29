"""
配额重置脚本（每日/每月）

对 user_quotas 中已过期的每日/每月周期执行重置，供 cron 或 Celery Beat 定时调用。

使用方法:
    # 预览将要重置的配额（不执行）
    uv run python scripts/reset_quota.py --dry-run

    # 执行重置
    uv run python scripts/reset_quota.py

建议 cron（每日 0:05 执行）:
    5 0 * * * cd /path/to/backend && uv run python scripts/reset_quota.py
"""

import argparse
import asyncio
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from domains.identity.infrastructure.repositories.user_quota_repository import (  # pylint: disable=wrong-import-position
    UserQuotaRepository,
)
from libs.db.database import get_session_context, init_db  # pylint: disable=wrong-import-position


async def run_reset(dry_run: bool = False) -> None:
    """执行配额重置"""
    await init_db()

    async with get_session_context() as db:
        repo = UserQuotaRepository(db)
        quotas = await repo.list_all()

        daily_count = 0
        monthly_count = 0

        for quota in quotas:
            if quota.needs_daily_reset():
                if not dry_run:
                    await repo.reset_daily_quota(quota.user_id)
                daily_count += 1
            if quota.needs_monthly_reset():
                if not dry_run:
                    await repo.reset_monthly_quota(quota.user_id)
                monthly_count += 1

        if dry_run:
            print(f"[预览] 将重置每日配额: {daily_count} 条, 每月配额: {monthly_count} 条")
        else:
            print(f"已重置每日配额: {daily_count} 条, 每月配额: {monthly_count} 条")


def main() -> None:
    parser = argparse.ArgumentParser(description="重置过期的每日/每月用户配额")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不执行重置",
    )
    args = parser.parse_args()
    asyncio.run(run_reset(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
