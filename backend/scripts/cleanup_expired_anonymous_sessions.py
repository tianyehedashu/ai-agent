"""
清理过期的匿名 Session

定期清理长期未使用的匿名用户 Session，释放数据库空间。
可以通过 cron 或其他调度器定期运行。

使用方法:
    # 预览将要清理的数据（不执行删除）
    uv run python scripts/cleanup_expired_anonymous_sessions.py --dry-run

    # 清理 30 天前的匿名 Session（默认）
    uv run python scripts/cleanup_expired_anonymous_sessions.py

    # 清理 7 天前的匿名 Session
    uv run python scripts/cleanup_expired_anonymous_sessions.py --days 7

    # 清理 90 天前的匿名 Session
    uv run python scripts/cleanup_expired_anonymous_sessions.py --days 90
"""

import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径（必须在导入项目模块之前）
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # pylint: disable=wrong-import-position
from sqlalchemy.ext.asyncio import (  # pylint: disable=wrong-import-position
    AsyncSession,
    create_async_engine,
)

from bootstrap.config_loader import get_app_config  # pylint: disable=wrong-import-position


async def get_engine():
    """获取数据库引擎"""
    config = get_app_config()
    return create_async_engine(config.infra.database_url, echo=False)


async def get_expired_anonymous_sessions(
    session: AsyncSession, cutoff_date: datetime
) -> list[tuple]:
    """获取过期的匿名 Session"""
    result = await session.execute(
        text("""
            SELECT s.id, s.title, s.anonymous_user_id, s.updated_at,
                   COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE s.anonymous_user_id IS NOT NULL
              AND s.updated_at < :cutoff_date
            GROUP BY s.id, s.title, s.anonymous_user_id, s.updated_at
            ORDER BY s.updated_at ASC
        """),
        {"cutoff_date": cutoff_date},
    )
    return result.fetchall()


async def delete_sessions(session: AsyncSession, session_ids: list[str]) -> int:
    """删除 Session（级联删除 Message）"""
    if not session_ids:
        return 0

    # 使用 IN 子句批量删除
    placeholders = ", ".join([f":id_{i}" for i in range(len(session_ids))])
    params = {f"id_{i}": sid for i, sid in enumerate(session_ids)}

    result = await session.execute(
        text(f"DELETE FROM sessions WHERE id IN ({placeholders}) RETURNING id"),
        params,
    )
    return len(result.fetchall())


async def cleanup_expired_sessions(days: int = 30, dry_run: bool = True) -> None:
    """清理过期的匿名 Session

    Args:
        days: 清理多少天前的 Session
        dry_run: 如果为 True，只预览不执行删除
    """
    engine = await get_engine()
    # 使用 naive datetime（与数据库中的 updated_at 一致）
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    async with AsyncSession(engine) as session:
        # 获取过期的匿名 Session
        expired_sessions = await get_expired_anonymous_sessions(session, cutoff_date)

        if not expired_sessions:
            print(f"没有找到 {days} 天前的匿名 Session，无需清理。")
            await engine.dispose()
            return

        total_messages = sum(s[4] for s in expired_sessions)
        print(f"\n找到 {len(expired_sessions)} 个过期的匿名 Session")
        print(f"关联的消息总数: {total_messages}")
        print(f"截止日期: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} ({days} 天前)")
        print("=" * 80)

        # 显示前 10 个
        for i, s in enumerate(expired_sessions[:10]):
            _session_id, title, anon_id, updated_at, msg_count = s
            title_display = title or "(无标题)"
            anon_display = anon_id[:16] + "..." if len(anon_id) > 16 else anon_id
            print(
                f"  {i + 1}. {title_display[:30]:<30} | "
                f"匿名ID: {anon_display:<20} | "
                f"消息: {msg_count:<5} | "
                f"更新: {updated_at.strftime('%Y-%m-%d')}"
            )

        if len(expired_sessions) > 10:
            print(f"  ... 还有 {len(expired_sessions) - 10} 个")

        print("=" * 80)

        if dry_run:
            print("\n[预览模式] 未执行任何删除操作")
            print("使用不带 --dry-run 参数执行实际清理")
            await engine.dispose()
            return

        # 执行删除
        session_ids = [str(s[0]) for s in expired_sessions]

        # 分批删除，每批 100 个
        batch_size = 100
        total_deleted = 0

        for i in range(0, len(session_ids), batch_size):
            batch = session_ids[i : i + batch_size]
            deleted = await delete_sessions(session, batch)
            total_deleted += deleted
            print(f"已删除批次 {i // batch_size + 1}: {deleted} 个 Session")

        await session.commit()

        print("\n" + "=" * 80)
        print("清理完成:")
        print(f"  - 删除 Session: {total_deleted} 个")
        print(f"  - 级联删除消息: {total_messages} 条")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="清理过期的匿名 Session")
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=30,
        help="清理多少天前的 Session（默认: 30 天）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="预览模式，不执行删除",
    )

    args = parser.parse_args()
    asyncio.run(cleanup_expired_sessions(days=args.days, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
