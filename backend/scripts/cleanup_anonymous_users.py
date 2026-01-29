"""
清理遗留的匿名用户记录

这个脚本用于清理 users 表中旧代码创建的匿名用户记录。
当前架构中，匿名用户不再存储到 users 表，而是：
1. 使用内存中的 Principal 对象
2. Session 通过 anonymous_user_id 字段关联

使用方法:
    # 预览将要清理的数据（不执行删除）
    uv run python scripts/cleanup_anonymous_users.py --dry-run

    # 执行清理
    uv run python scripts/cleanup_anonymous_users.py

    # 强制删除（包括有关联 Session 的匿名用户）
    uv run python scripts/cleanup_anonymous_users.py --force
"""

import argparse
import asyncio
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


async def get_anonymous_users(session: AsyncSession) -> list[tuple]:
    """获取所有匿名用户"""
    result = await session.execute(
        text("""
            SELECT id, email, name, created_at
            FROM users
            WHERE email LIKE 'anonymous-%@local'
            ORDER BY created_at DESC
        """)
    )
    return result.fetchall()


async def get_sessions_by_user_id(session: AsyncSession, user_id: str) -> list[tuple]:
    """获取用户关联的 Session"""
    result = await session.execute(
        text("SELECT id, title, created_at FROM sessions WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    return result.fetchall()


async def migrate_session_to_anonymous(
    session: AsyncSession, session_id: str, anonymous_user_id: str
) -> None:
    """将 Session 从 user_id 迁移到 anonymous_user_id"""
    await session.execute(
        text("""
            UPDATE sessions
            SET user_id = NULL, anonymous_user_id = :anonymous_user_id
            WHERE id = :session_id
        """),
        {"session_id": session_id, "anonymous_user_id": anonymous_user_id},
    )


async def delete_user(session: AsyncSession, user_id: str) -> None:
    """删除用户记录"""
    await session.execute(
        text("DELETE FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )


def extract_anonymous_id_from_email(email: str) -> str:
    """从邮箱中提取 anonymous_user_id

    邮箱格式: anonymous-{uuid}@local
    返回: {uuid}
    """
    # 移除 'anonymous-' 前缀和 '@local' 后缀
    if email.startswith("anonymous-") and email.endswith("@local"):
        return email[10:-6]  # len("anonymous-") = 10, len("@local") = 6
    return email


async def cleanup_anonymous_users(  # pylint: disable=too-many-branches,too-many-statements
    dry_run: bool = True, force: bool = False
) -> None:
    """清理匿名用户记录

    CLI 主流程分支多，拆分为更小函数会降低可读性；可后续按子步骤重构。

    Args:
        dry_run: 如果为 True，只预览不执行删除
        force: 如果为 True，强制删除有关联 Session 的用户（Session 会被迁移）
    """
    engine = await get_engine()

    async with AsyncSession(engine) as session:
        # 获取所有匿名用户
        anonymous_users = await get_anonymous_users(session)

        if not anonymous_users:
            print("没有找到匿名用户记录，无需清理。")
            await engine.dispose()
            return

        print(f"\n找到 {len(anonymous_users)} 个匿名用户记录")
        print("=" * 80)

        users_to_delete = []
        users_with_sessions = []

        for user in anonymous_users:
            user_id, email, name, created_at = user
            anonymous_id = extract_anonymous_id_from_email(email)

            # 检查关联的 Session
            sessions = await get_sessions_by_user_id(session, str(user_id))

            if sessions:
                users_with_sessions.append((user_id, email, name, anonymous_id, sessions))
                print(f"\n[有关联数据] {email}")
                print(f"  - 用户ID: {user_id}")
                print(f"  - 创建时间: {created_at}")
                print(f"  - 关联 Session 数: {len(sessions)}")
                for s in sessions[:3]:  # 只显示前3个
                    print(f"    - {s[0]}: {s[1] or '(无标题)'}")
                if len(sessions) > 3:
                    print(f"    - ... 还有 {len(sessions) - 3} 个")
            else:
                users_to_delete.append((user_id, email, name))
                print(f"\n[可安全删除] {email}")
                print(f"  - 用户ID: {user_id}")
                print(f"  - 创建时间: {created_at}")

        print("\n" + "=" * 80)
        print("统计:")
        print(f"  - 可安全删除: {len(users_to_delete)} 个")
        print(f"  - 有关联数据: {len(users_with_sessions)} 个")

        if dry_run:
            print("\n[预览模式] 未执行任何删除操作")
            print("使用 --no-dry-run 或不带 --dry-run 参数执行实际清理")
            await engine.dispose()
            return

        # 执行删除
        deleted_count = 0
        migrated_sessions = 0

        # 1. 删除没有关联数据的用户
        for user_id, email, _ in users_to_delete:
            await delete_user(session, str(user_id))
            deleted_count += 1
            print(f"已删除: {email}")

        # 2. 处理有关联 Session 的用户
        if users_with_sessions:
            if force:
                print("\n[强制模式] 迁移 Session 并删除用户...")
                for user_id, email, _, anonymous_id, sessions in users_with_sessions:
                    # 迁移所有 Session
                    for s in sessions:
                        await migrate_session_to_anonymous(session, str(s[0]), anonymous_id)
                        migrated_sessions += 1
                    # 删除用户
                    await delete_user(session, str(user_id))
                    deleted_count += 1
                    print(f"已迁移并删除: {email} ({len(sessions)} 个 Session)")
            else:
                print(f"\n[跳过] {len(users_with_sessions)} 个有关联数据的用户未删除")
                print("使用 --force 参数强制迁移并删除")

        await session.commit()

        print("\n" + "=" * 80)
        print("清理完成:")
        print(f"  - 删除用户: {deleted_count} 个")
        print(f"  - 迁移 Session: {migrated_sessions} 个")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="清理遗留的匿名用户记录")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="预览模式，不执行删除（默认：执行删除）",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="强制删除有关联 Session 的用户（Session 会被迁移到 anonymous_user_id）",
    )

    args = parser.parse_args()
    asyncio.run(cleanup_anonymous_users(dry_run=args.dry_run, force=args.force))


if __name__ == "__main__":
    main()
